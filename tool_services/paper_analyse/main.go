package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"rsc.io/pdf"
)

const (
	defaultListenAddr = ":3000"
	maxUploadSize     = 50 << 20 // 50 MiB
	requestTimeout    = 2 * time.Minute

	// TextRank limits (avoid extremely large PDFs causing O(n^2) blowups)
	maxExtractedTextChars = 300_000
	maxSentences          = 200
	maxChunks             = 400
)

// ---- Standard artifacts (Doc / Chunks / Summary) ----
type Doc struct {
	DocID         string   `json:"doc_id"`
	CanonicalID   string   `json:"canonical_id,omitempty"` // doi/arxiv
	Title         string   `json:"title,omitempty"`
	Authors       []string `json:"authors,omitempty"`
	Year          int      `json:"year,omitempty"`
	Venue         string   `json:"venue,omitempty"`
	Source        string   `json:"source,omitempty"`
	License       string   `json:"license,omitempty"`
	OpenAccess    *bool    `json:"open_access,omitempty"`
	PdfObjectKey  string   `json:"pdf_object_key,omitempty"` // MinIO object path if known
	PdfSha256     string   `json:"pdf_sha256"`
	OriginalName  string   `json:"original_filename,omitempty"`
	CreatedAtUnix int64    `json:"created_at_unix"`
}

type Span struct {
	Page      int `json:"page,omitempty"`
	Paragraph int `json:"paragraph,omitempty"`
}

type Chunk struct {
	ChunkID     string `json:"chunk_id"`
	DocID       string `json:"doc_id"`
	Text        string `json:"text"`
	Span        Span   `json:"span,omitempty"`
	SectionPath string `json:"section_path,omitempty"`
}

type SummaryKeywords struct {
	Summary        string   `json:"summary"`
	SummarySource  string   `json:"summary_source"` // abstract_from_pdf / generated_summary
	Keywords       []string `json:"keywords"`
	Abstract       string   `json:"abstract,omitempty"`
	AbstractSource string   `json:"abstract_source,omitempty"` // extracted / missing
}

func main() {
	gin.SetMode(gin.ReleaseMode)
	router := gin.Default()

	router.MaxMultipartMemory = maxUploadSize

	router.Static("/static", "./web")
	router.GET("/", func(c *gin.Context) {
		c.File("./web/index.html")
	})

	router.POST("/api/convert", convertHandler)

	addr := getEnv("LISTEN_ADDR", defaultListenAddr)
	log.Printf("Starting server on %s (pipeline: PDF -> TextRank -> Summary+Keywords)", addr)
	if err := router.Run(addr); err != nil {
		log.Fatalf("failed to start server: %v", err)
	}
}

func convertHandler(c *gin.Context) {
	fileHeader, err := c.FormFile("file")
	if errors.Is(err, http.ErrMissingFile) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing file field \"file\""})
		return
	}
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("read form file failed: %v", err)})
		return
	}

	file, err := fileHeader.Open()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("unable to open uploaded file: %v", err)})
		return
	}
	defer file.Close()

	start := time.Now()
	pdfBytes, err := io.ReadAll(io.LimitReader(file, maxUploadSize+1))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("read uploaded file failed: %v", err)})
		return
	}
	if int64(len(pdfBytes)) > maxUploadSize {
		c.JSON(http.StatusRequestEntityTooLarge, gin.H{"error": "file too large"})
		return
	}

	// Basic magic check to avoid panics / confusing errors when input isn't a real PDF.
	if !looksLikePDF(pdfBytes) {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "uploaded content does not look like a PDF (missing %PDF header)",
		})
		return
	}

	pdfSha := sha256Hex(pdfBytes)
	// Allow upstream to provide stable doc_id for idempotency / state machine.
	docID := strings.TrimSpace(c.PostForm("doc_id"))
	if docID == "" {
		docID = newID()
	}

	// Optional metadata (passed by coordinator/indexer)
	canonicalID := strings.TrimSpace(c.PostForm("canonical_id"))
	source := strings.TrimSpace(c.PostForm("source"))
	pdfObjectKey := strings.TrimSpace(c.PostForm("pdf_object_key"))
	title := strings.TrimSpace(c.PostForm("title"))
	authors := parseCSV(c.PostForm("authors"))
	year := parseYear(c.PostForm("year"))
	venue := strings.TrimSpace(c.PostForm("venue"))
	license := strings.TrimSpace(c.PostForm("license"))
	openAccess := parseBoolPtr(c.PostForm("open_access"))

	text, err := extractTextFromPDF(pdfBytes)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("extract text failed: %v", err)})
		return
	}
	if len(text) > maxExtractedTextChars {
		text = text[:maxExtractedTextChars]
	}

	// Heuristic metadata extraction (best-effort)
	if canonicalID == "" {
		canonicalID = inferCanonicalID(fileHeader.Filename, text)
	}
	if title == "" {
		title = inferTitle(text)
	}
	if len(authors) == 0 {
		authors = inferAuthors(text)
	}
	if year == 0 {
		year = inferYear(text)
	}

	abstract, absOK := extractAbstract(text)
	absSource := "missing"
	if absOK {
		absSource = "extracted"
	}
	sum, keywords := textrankSummarizeAndKeywords(func() string {
		if absOK {
			return abstract
		}
		return text
	}())
	sumSource := "generated_summary"
	if absOK && strings.TrimSpace(abstract) != "" {
		sumSource = "abstract_from_pdf"
	}

	doc := Doc{
		DocID:         docID,
		CanonicalID:   canonicalID,
		Title:         title,
		Authors:       authors,
		Year:          year,
		Venue:         venue,
		Source:        source,
		License:       license,
		OpenAccess:    openAccess,
		PdfObjectKey:  pdfObjectKey,
		PdfSha256:     pdfSha,
		OriginalName:  fileHeader.Filename,
		CreatedAtUnix: time.Now().Unix(),
	}

	chunks := buildChunks(docID, text)
	out := struct {
		Doc         Doc             `json:"doc"`
		Chunks      []Chunk         `json:"chunks"`
		Summary     SummaryKeywords `json:"summary_keywords"`
		ElapsedMS   int64           `json:"elapsed_ms"`
		TextPreview string          `json:"text_preview,omitempty"`
	}{
		Doc:    doc,
		Chunks: chunks,
		Summary: SummaryKeywords{
			Summary:        sum,
			SummarySource:  sumSource,
			Keywords:       keywords,
			Abstract:       abstract,
			AbstractSource: absSource,
		},
		ElapsedMS:   time.Since(start).Milliseconds(),
		TextPreview: preview(text, 2000),
	}

	c.JSON(http.StatusOK, out)
}

func extractTextFromPDF(pdfBytes []byte) (out string, err error) {
	// First try pure-Go parser (fast, no external deps). If it fails on some PDFs,
	// fallback to `pdftotext` (Poppler) if installed.
	if txt, e := extractTextWithRscPDF(pdfBytes); e == nil && strings.TrimSpace(txt) != "" {
		return txt, nil
	}
	// Fallback (more robust for real-world PDFs)
	ctx, cancel := context.WithTimeout(context.Background(), requestTimeout)
	defer cancel()
	if txt, e := extractTextWithPDFToText(ctx, pdfBytes); e == nil && strings.TrimSpace(txt) != "" {
		return txt, nil
	} else if e != nil {
		return "", e
	}
	return "", fmt.Errorf("unable to extract text (no extractor succeeded)")
}

func looksLikePDF(b []byte) bool {
	// Skip UTF-8 BOM / whitespace
	i := 0
	for i < len(b) {
		c := b[i]
		if c == 0xEF && i+2 < len(b) && b[i+1] == 0xBB && b[i+2] == 0xBF {
			i += 3
			continue
		}
		if c == ' ' || c == '\n' || c == '\r' || c == '\t' {
			i++
			continue
		}
		break
	}
	return i+4 <= len(b) && bytes.HasPrefix(b[i:], []byte("%PDF"))
}

func sha256Hex(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func newID() string {
	// Simple unique id without extra deps: time-based + random-ish from sha256
	raw := fmt.Sprintf("%d-%d", time.Now().UnixNano(), os.Getpid())
	h := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(h[:16])
}

func parseCSV(s string) []string {
	s = strings.TrimSpace(s)
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ",")
	var out []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}

func parseYear(s string) int {
	s = strings.TrimSpace(s)
	if s == "" {
		return 0
	}
	n, _ := strconv.Atoi(s)
	if n < 1900 || n > 2100 {
		return 0
	}
	return n
}

func parseBoolPtr(s string) *bool {
	s = strings.TrimSpace(strings.ToLower(s))
	if s == "" {
		return nil
	}
	v := s == "1" || s == "true" || s == "yes" || s == "y"
	return &v
}

func preview(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func inferCanonicalID(filename string, text string) string {
	// arXiv id like 1706.03762
	re := regexp.MustCompile(`\b(\d{4}\.\d{4,5})(v\d+)?\b`)
	if m := re.FindStringSubmatch(filename); len(m) > 0 {
		return "arxiv:" + m[1]
	}
	if m := re.FindStringSubmatch(text); len(m) > 0 {
		return "arxiv:" + m[1]
	}
	// DOI rough
	reDoi := regexp.MustCompile(`\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b`)
	if m := reDoi.FindString(text); m != "" {
		return "doi:" + m
	}
	return ""
}

func inferTitle(text string) string {
	// Heuristic: first non-empty line before "Abstract"
	lines := strings.Split(text, "\n")
	for i := 0; i < len(lines) && i < 40; i++ {
		ln := strings.TrimSpace(lines[i])
		if ln == "" {
			continue
		}
		if strings.EqualFold(ln, "abstract") {
			break
		}
		// Avoid common headers
		if len(ln) >= 10 && len(ln) <= 200 {
			return ln
		}
	}
	return ""
}

func inferAuthors(text string) []string {
	// Very rough: line after title, split by commas
	lines := strings.Split(text, "\n")
	title := inferTitle(text)
	for i := 0; i < len(lines)-1 && i < 60; i++ {
		if strings.TrimSpace(lines[i]) == title {
			cand := strings.TrimSpace(lines[i+1])
			if cand == "" || strings.Contains(strings.ToLower(cand), "abstract") {
				return nil
			}
			return parseCSV(strings.ReplaceAll(cand, " and ", ","))
		}
	}
	return nil
}

func inferYear(text string) int {
	reY := regexp.MustCompile(`\b(19\d{2}|20\d{2})\b`)
	all := reY.FindAllString(text, 10)
	best := 0
	for _, y := range all {
		n, _ := strconv.Atoi(y)
		if n > best {
			best = n
		}
	}
	if best < 1900 || best > 2100 {
		return 0
	}
	return best
}

func extractAbstract(text string) (string, bool) {
	lower := strings.ToLower(text)
	i := strings.Index(lower, "\nabstract")
	if i < 0 {
		i = strings.Index(lower, " abstract")
	}
	if i < 0 {
		return "", false
	}
	// Find next section marker (introduction)
	j := strings.Index(lower[i:], "introduction")
	end := len(text)
	if j > 0 {
		end = i + j
	}
	abs := strings.TrimSpace(text[i:end])
	abs = strings.TrimPrefix(abs, "Abstract")
	abs = strings.TrimPrefix(abs, "abstract")
	abs = strings.TrimSpace(abs)
	if len(abs) < 50 {
		return "", false
	}
	if len(abs) > 4000 {
		abs = abs[:4000]
	}
	return abs, true
}

func buildChunks(docID string, text string) []Chunk {
	// Very simple: sentence-based chunks grouped into paragraphs; span uses paragraph index.
	sents := splitSentences(text)
	if len(sents) == 0 {
		return nil
	}
	sections := inferSectionPaths(sents)
	var out []Chunk
	para := 0
	for i := 0; i < len(sents); i++ {
		para++
		chText := strings.TrimSpace(sents[i])
		if chText == "" {
			continue
		}
		out = append(out, Chunk{
			ChunkID:     newID(),
			DocID:       docID,
			Text:        cleanChunkText(chText),
			Span:        Span{Paragraph: para},
			SectionPath: sections[i],
		})
		if len(out) >= maxChunks {
			break
		}
	}
	return out
}

func cleanChunkText(s string) string {
	s = normalizeText(s)
	// strip duplicated spaces
	s = reSpace.ReplaceAllString(s, " ")
	return strings.TrimSpace(s)
}

func inferSectionPaths(sents []string) []string {
	// Heuristic: detect headings like "3 Method" or "3.2 Training" and keep last seen.
	out := make([]string, len(sents))
	cur := ""
	reHead := regexp.MustCompile(`^\s*(\d+(\.\d+)*)\s+([A-Z][A-Za-z].{0,80})$`)
	for i, s := range sents {
		line := strings.TrimSpace(s)
		// only treat short lines as headings
		if len(line) <= 90 {
			if m := reHead.FindStringSubmatch(line); len(m) > 0 {
				cur = m[1] + " " + strings.TrimSpace(m[3])
			}
		}
		out[i] = cur
	}
	return out
}

func extractTextWithRscPDF(pdfBytes []byte) (out string, err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("rsc.io/pdf panic: %v", r)
			out = ""
		}
	}()

	r := bytes.NewReader(pdfBytes) // io.ReaderAt
	reader, err := pdf.NewReader(r, int64(len(pdfBytes)))
	if err != nil {
		return "", err
	}

	var sb strings.Builder
	n := reader.NumPage()
	for i := 1; i <= n; i++ {
		p := reader.Page(i)
		if p.V.IsNull() {
			continue
		}
		content := p.Content()
		for _, t := range content.Text {
			sb.WriteString(t.S)
			sb.WriteString(" ")
			if sb.Len() > maxExtractedTextChars {
				break
			}
		}
		sb.WriteString("\n")
		if sb.Len() > maxExtractedTextChars {
			break
		}
	}
	return normalizeText(sb.String()), nil
}

func extractTextWithPDFToText(ctx context.Context, pdfBytes []byte) (string, error) {
	// pdftotext reads from file; write to temp.
	tmpDir := os.TempDir()
	inPath := filepath.Join(tmpDir, fmt.Sprintf("mico-%d.pdf", time.Now().UnixNano()))
	defer os.Remove(inPath)
	if err := os.WriteFile(inPath, pdfBytes, 0o600); err != nil {
		return "", err
	}

	bin := os.Getenv("PDFTOTEXT_BIN")
	if bin == "" {
		bin = "pdftotext"
	}
	// Output to stdout by using "-" as output file.
	cmd := exec.CommandContext(ctx, bin, "-enc", "UTF-8", "-nopgbrk", "-layout", inPath, "-")
	out, err := cmd.Output()
	if err != nil {
		// Include stderr if available
		if ee := (*exec.ExitError)(nil); errors.As(err, &ee) {
			return "", fmt.Errorf("pdftotext failed: %v: %s", err, string(ee.Stderr))
		}
		return "", fmt.Errorf("pdftotext failed: %v", err)
	}
	return normalizeText(string(out)), nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ---- TextRank (Summary + Keywords) ----

var (
	reSpace      = regexp.MustCompile(`\s+`)
	reWord       = regexp.MustCompile(`[a-z0-9]+`)
)

func normalizeText(s string) string {
	s = strings.ReplaceAll(s, "\u0000", " ")
	s = strings.ReplaceAll(s, "\r", " ")
	s = reSpace.ReplaceAllString(s, " ")
	return strings.TrimSpace(s)
}

func splitSentences(text string) []string {
	text = strings.TrimSpace(text)
	if text == "" {
		return nil
	}
	var out []string
	var buf strings.Builder

	flush := func() {
		s := strings.TrimSpace(buf.String())
		buf.Reset()
		if len(s) < 20 {
			return
		}
		out = append(out, s)
	}

	for _, r := range text {
		buf.WriteRune(r)
		if isSentenceEnd(r) {
			flush()
			if len(out) >= maxSentences {
				return out
			}
		}
	}
	flush()

	if len(out) == 0 {
		// Fallback: split by newline
		lines := strings.Split(text, "\n")
		for _, ln := range lines {
			ln = strings.TrimSpace(ln)
			if len(ln) < 20 {
				continue
			}
			out = append(out, ln)
			if len(out) >= maxSentences {
				break
			}
		}
	}
	return out
}

func isSentenceEnd(r rune) bool {
	switch r {
	case '.', '!', '?', '。', '！', '？', ';', '；', '\n':
		return true
	default:
		return false
	}
}

func tokens(s string) []string {
	s = strings.ToLower(s)
	words := reWord.FindAllString(s, -1)
	out := make([]string, 0, len(words))
	for _, w := range words {
		if len(w) < 3 {
			continue
		}
		if stopwords[w] {
			continue
		}
		out = append(out, w)
	}
	return out
}

func textrankSummarizeAndKeywords(text string) (string, []string) {
	sents := splitSentences(text)
	if len(sents) == 0 {
		return "", nil
	}
	// Keyword graph (word co-occurrence)
	kwScores := textrankKeywords(text, 10)

	// Sentence scoring (TextRank sentence graph)
	scores := textrankSentences(sents)
	type pair struct {
		Idx   int
		Score float64
	}
	ranked := make([]pair, 0, len(scores))
	for i, sc := range scores {
		ranked = append(ranked, pair{Idx: i, Score: sc})
	}
	sort.Slice(ranked, func(i, j int) bool { return ranked[i].Score > ranked[j].Score })

	// pick top K and keep original order
	k := 5
	if len(ranked) < k {
		k = len(ranked)
	}
	chosen := ranked[:k]
	sort.Slice(chosen, func(i, j int) bool { return chosen[i].Idx < chosen[j].Idx })

	var sb strings.Builder
	for i, p := range chosen {
		if i > 0 {
			sb.WriteString("\n")
		}
		sb.WriteString(sents[p.Idx])
	}
	return sb.String(), kwScores
}

func textrankKeywords(text string, topK int) []string {
	words := tokens(text)
	if len(words) == 0 {
		return nil
	}
	window := 4
	graph := map[string]map[string]float64{}
	for i := 0; i < len(words); i++ {
		w := words[i]
		if graph[w] == nil {
			graph[w] = map[string]float64{}
		}
		for j := i + 1; j < len(words) && j <= i+window; j++ {
			u := words[j]
			if u == w {
				continue
			}
			if graph[u] == nil {
				graph[u] = map[string]float64{}
			}
			graph[w][u] += 1
			graph[u][w] += 1
		}
	}
	pr := pagerank(graph, 20, 0.85)
	type kv struct {
		K string
		V float64
	}
	arr := make([]kv, 0, len(pr))
	for k, v := range pr {
		arr = append(arr, kv{K: k, V: v})
	}
	sort.Slice(arr, func(i, j int) bool { return arr[i].V > arr[j].V })
	if topK > len(arr) {
		topK = len(arr)
	}
	out := make([]string, 0, topK)
	for i := 0; i < topK; i++ {
		out = append(out, arr[i].K)
	}
	return out
}

func textrankSentences(sents []string) []float64 {
	n := len(sents)
	if n == 0 {
		return nil
	}
	// Pre-tokenize
	ws := make([][]string, n)
	for i := 0; i < n; i++ {
		ws[i] = tokens(sents[i])
	}
	graph := map[int]map[int]float64{}
	for i := 0; i < n; i++ {
		graph[i] = map[int]float64{}
	}
	for i := 0; i < n; i++ {
		for j := i + 1; j < n; j++ {
			sim := sentenceSimilarity(ws[i], ws[j])
			if sim <= 0 {
				continue
			}
			graph[i][j] = sim
			graph[j][i] = sim
		}
	}
	pr := pagerankInt(graph, 20, 0.85)
	out := make([]float64, n)
	for i := 0; i < n; i++ {
		out[i] = pr[i]
	}
	return out
}

func sentenceSimilarity(a, b []string) float64 {
	if len(a) == 0 || len(b) == 0 {
		return 0
	}
	set := map[string]int{}
	for _, w := range a {
		set[w]++
	}
	inter := 0
	for _, w := range b {
		if set[w] > 0 {
			inter++
		}
	}
	if inter == 0 {
		return 0
	}
	den := math.Log(float64(len(a))) + math.Log(float64(len(b)))
	if den == 0 {
		return 0
	}
	return float64(inter) / den
}

// PageRank for string-keyed graph
func pagerank(graph map[string]map[string]float64, iters int, d float64) map[string]float64 {
	nodes := make([]string, 0, len(graph))
	for n := range graph {
		nodes = append(nodes, n)
	}
	nn := float64(len(nodes))
	score := map[string]float64{}
	for _, n := range nodes {
		score[n] = 1.0 / nn
	}
	for t := 0; t < iters; t++ {
		next := map[string]float64{}
		for _, n := range nodes {
			next[n] = (1 - d) / nn
		}
		for _, u := range nodes {
			out := graph[u]
			sumW := 0.0
			for _, w := range out {
				sumW += w
			}
			if sumW == 0 {
				continue
			}
			for v, w := range out {
				next[v] += d * score[u] * (w / sumW)
			}
		}
		score = next
	}
	return score
}

// PageRank for int-keyed graph
func pagerankInt(graph map[int]map[int]float64, iters int, d float64) map[int]float64 {
	nodes := make([]int, 0, len(graph))
	for n := range graph {
		nodes = append(nodes, n)
	}
	nn := float64(len(nodes))
	score := map[int]float64{}
	for _, n := range nodes {
		score[n] = 1.0 / nn
	}
	for t := 0; t < iters; t++ {
		next := map[int]float64{}
		for _, n := range nodes {
			next[n] = (1 - d) / nn
		}
		for _, u := range nodes {
			out := graph[u]
			sumW := 0.0
			for _, w := range out {
				sumW += w
			}
			if sumW == 0 {
				continue
			}
			for v, w := range out {
				next[v] += d * score[u] * (w / sumW)
			}
		}
		score = next
	}
	return score
}

var stopwords = map[string]bool{
	"the": true, "and": true, "for": true, "that": true, "with": true, "this": true, "from": true, "are": true,
	"was": true, "were": true, "have": true, "has": true, "had": true, "not": true, "but": true, "can": true,
	"will": true, "would": true, "should": true, "could": true, "into": true, "over": true, "under": true,
	"between": true, "within": true, "without": true, "also": true, "we": true, "our": true, "they": true,
	"their": true, "them": true, "you": true, "your": true, "i": true, "me": true, "my": true, "in": true,
	"on": true, "at": true, "to": true, "of": true, "a": true, "an": true, "as": true, "is": true, "it": true,
}

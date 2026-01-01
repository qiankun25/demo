package translation

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"regexp"
	"strings"
	"time"
)

// TextTranslateRequest represents a text translation request
type TextTranslateRequest struct {
	SourceLang  string    `json:"source_lang"`
	TargetLang  string    `json:"target_lang"`
	Content     string    `json:"content"`
	ContentType string    `json:"content_type"` // plain, markdown, latex
	Domain      string    `json:"domain"`
	Style       Style     `json:"style"`
	Glossary    *Glossary `json:"glossary,omitempty"`
	Options     struct {
		ReturnAlignment bool `json:"return_alignment"`
		ReturnQuality   bool `json:"return_quality"`
	} `json:"options"`
}

// TextTranslateResponse represents a text translation response
type TextTranslateResponse struct {
	Translation  string       `json:"translation"`
	Alignment    []Alignment  `json:"alignment,omitempty"`
	GlossaryHits []TermHit    `json:"glossary_hits,omitempty"`
	Quality      *QualityReport `json:"quality,omitempty"`
	TraceID      string       `json:"trace_id"`
}

// Alignment represents source-target alignment
type Alignment struct {
	SrcSpan []int `json:"src_span"`
	TgtSpan []int `json:"tgt_span"`
}

// TermHit represents a glossary term hit
type TermHit struct {
	Source   string `json:"source"`
	Target   string `json:"target"`
	Position int    `json:"position"`
}

// QualityReport represents quality assessment results
type QualityReport struct {
	Score              float64  `json:"score"`
	Issues             []string `json:"issues"`
	GlossaryHitRate    float64  `json:"glossary_hit_rate"`
	NumberConsistency  bool     `json:"number_consistency"`
}

// ProtectedRegion represents a protected region in text
type ProtectedRegion struct {
	Type      string // latex, code, url, doi, citation
	Start     int
	End       int
	Content   string
	Placeholder string
}

// GlossaryService interface for glossary operations
type GlossaryService interface {
	LoadGlossary(ctx context.Context, projectID string) (Glossary, error)
}

// QualityService interface for quality assessment
type QualityService interface {
	Assess(ctx context.Context, source, target string, glossary Glossary) *QualityReport
}

// Cache interface for caching
type Cache interface {
	Get(ctx context.Context, key string) interface{}
	Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error
}

// TextTranslator handles text translation
type TextTranslator struct {
	engine      TranslationEngine
	glossarySvc GlossaryService
	qualitySvc  QualityService
	cache       Cache
}

// NewTextTranslator creates a new text translator
func NewTextTranslator(engine TranslationEngine, glossarySvc GlossaryService, qualitySvc QualityService, cache Cache) *TextTranslator {
	return &TextTranslator{
		engine:      engine,
		glossarySvc: glossarySvc,
		qualitySvc:  qualitySvc,
		cache:       cache,
	}
}

// Translate performs text translation
func (t *TextTranslator) Translate(ctx context.Context, req *TextTranslateRequest) (*TextTranslateResponse, error) {
	// 1. Normalize text
	normalized := normalizeText(req.Content)

	// 2. Check cache
	cacheKey := buildCacheKey(normalized, req)
	if cached := t.cache.Get(ctx, cacheKey); cached != nil {
		if resp, ok := cached.(*TextTranslateResponse); ok {
			return resp, nil
		}
	}

	// 3. Segment text
	segments := segmentText(normalized, req.ContentType)

	// 4. Protect regions (LaTeX, code blocks, URLs, DOI, citations)
	protected, regions := protectRegions(segments)

	// 5. Load glossary and build term mask
	var glossary Glossary
	if req.Glossary != nil {
		glossary = *req.Glossary
	} else if req.Glossary != nil && req.Glossary.ProjectID != "" {
		loaded, err := t.glossarySvc.LoadGlossary(ctx, req.Glossary.ProjectID)
		if err == nil {
			glossary = loaded
		}
	}
	termMask := buildTermMask(protected, glossary)

	// 6. Basic translation
	translateReq := &TranslateRequest{
		SourceLang: req.SourceLang,
		TargetLang: req.TargetLang,
		Text:       protected,
		Style:      req.Style,
	}
	draft, err := t.engine.Translate(ctx, translateReq)
	if err != nil {
		return nil, fmt.Errorf("translation failed: %w", err)
	}

	// 7. Post-edit with glossary and style
	edited, err := t.engine.PostEdit(ctx, draft, glossary, req.Style)
	if err != nil {
		edited = draft // Fallback to draft if post-edit fails
	}

	// 8. Enforce glossary terms
	final := enforceGlossary(edited, glossary, termMask)

	// 9. Restore protected regions
	restored := restoreRegions(final, regions)

	// 10. Quality assessment
	var quality *QualityReport
	if req.Options.ReturnQuality {
		quality = t.qualitySvc.Assess(ctx, normalized, restored, glossary)
	}

	// 11. Build response
	result := &TextTranslateResponse{
		Translation: restored,
		Quality:     quality,
		TraceID:     generateTraceID(),
	}

	// Find glossary hits
	if glossary.ProjectID != "" {
		hits := findGlossaryHits(normalized, glossary)
		result.GlossaryHits = hits
	}

	// 12. Cache result
	t.cache.Set(ctx, cacheKey, result, 24*time.Hour)

	return result, nil
}

// normalizeText normalizes Unicode, full-width/half-width, whitespace
func normalizeText(text string) string {
	// Convert full-width to half-width
	text = strings.ReplaceAll(text, "　", " ")
	// Normalize whitespace
	text = regexp.MustCompile(`\s+`).ReplaceAllString(text, " ")
	return strings.TrimSpace(text)
}

// segmentText segments text by paragraphs/sentences
func segmentText(text, contentType string) []string {
	if contentType == "latex" {
		// For LaTeX, preserve structure
		return []string{text}
	}
	// Simple paragraph segmentation
	paragraphs := strings.Split(text, "\n\n")
	var segments []string
	for _, p := range paragraphs {
		p = strings.TrimSpace(p)
		if p != "" {
			segments = append(segments, p)
		}
	}
	return segments
}

// protectRegions marks protected regions and replaces with placeholders
func protectRegions(segments []string) (string, []ProtectedRegion) {
	var regions []ProtectedRegion
	var result strings.Builder
	placeholderIndex := 0

	for _, segment := range segments {
		text := segment
		offset := result.Len()

		// Protect LaTeX: $...$, \(...\), \[...\], \begin{equation}...\end{equation}
		latexPatterns := []*regexp.Regexp{
			regexp.MustCompile(`\$[^$]+\$`),
			regexp.MustCompile(`\\\([^)]+\\\)`),
			regexp.MustCompile(`\\\[[^\]]+\\\]`),
			regexp.MustCompile(`\\begin\{equation\}.*?\\end\{equation\}`),
		}

		for _, pattern := range latexPatterns {
			matches := pattern.FindAllStringIndex(text, -1)
			for i := len(matches) - 1; i >= 0; i-- {
				match := matches[i]
				placeholder := fmt.Sprintf("__LATEX_%d__", placeholderIndex)
				placeholderIndex++
				regions = append(regions, ProtectedRegion{
					Type:        "latex",
					Start:       offset + match[0],
					End:         offset + match[1],
					Content:     text[match[0]:match[1]],
					Placeholder: placeholder,
				})
				text = text[:match[0]] + placeholder + text[match[1]:]
			}
		}

		// Protect code blocks: ```...```
		codePattern := regexp.MustCompile("```[^`]+```")
		matches := codePattern.FindAllStringIndex(text, -1)
		for i := len(matches) - 1; i >= 0; i-- {
			match := matches[i]
			placeholder := fmt.Sprintf("__CODE_%d__", placeholderIndex)
			placeholderIndex++
			regions = append(regions, ProtectedRegion{
				Type:        "code",
				Start:       offset + match[0],
				End:         offset + match[1],
				Content:     text[match[0]:match[1]],
				Placeholder: placeholder,
			})
			text = text[:match[0]] + placeholder + text[match[1]:]
		}

		// Protect URLs
		urlPattern := regexp.MustCompile(`https?://[^\s]+`)
		matches = urlPattern.FindAllStringIndex(text, -1)
		for i := len(matches) - 1; i >= 0; i-- {
			match := matches[i]
			placeholder := fmt.Sprintf("__URL_%d__", placeholderIndex)
			placeholderIndex++
			regions = append(regions, ProtectedRegion{
				Type:        "url",
				Start:       offset + match[0],
				End:         offset + match[1],
				Content:     text[match[0]:match[1]],
				Placeholder: placeholder,
			})
			text = text[:match[0]] + placeholder + text[match[1]:]
		}

		// Protect citations: [1], (Smith et al., 2020)
		citationPattern := regexp.MustCompile(`\[(\d+)\]|\([A-Z][a-z]+ et al\.?, \d{4}\)`)
		matches = citationPattern.FindAllStringIndex(text, -1)
		for i := len(matches) - 1; i >= 0; i-- {
			match := matches[i]
			placeholder := fmt.Sprintf("__CITATION_%d__", placeholderIndex)
			placeholderIndex++
			regions = append(regions, ProtectedRegion{
				Type:        "citation",
				Start:       offset + match[0],
				End:         offset + match[1],
				Content:     text[match[0]:match[1]],
				Placeholder: placeholder,
			})
			text = text[:match[0]] + placeholder + text[match[1]:]
		}

		result.WriteString(text)
		if len(segments) > 1 {
			result.WriteString("\n\n")
		}
	}

	return result.String(), regions
}

// buildTermMask builds a term mask for glossary enforcement
func buildTermMask(text string, glossary Glossary) map[string]bool {
	mask := make(map[string]bool)
	for _, term := range glossary.Terms {
		if term.CaseSensitive {
			if strings.Contains(text, term.SourceText) {
				mask[term.SourceText] = true
			}
		} else {
			if strings.Contains(strings.ToLower(text), strings.ToLower(term.SourceText)) {
				mask[term.SourceText] = true
			}
		}
	}
	return mask
}

// enforceGlossary enforces glossary terms in translated text
func enforceGlossary(text string, glossary Glossary, mask map[string]bool) string {
	result := text
	for _, term := range glossary.Terms {
		if mask[term.SourceText] {
			// Simple replacement (can be enhanced with word boundary matching)
			if term.CaseSensitive {
				result = strings.ReplaceAll(result, term.SourceText, term.TargetText)
			} else {
				// Case-insensitive replacement
				re := regexp.MustCompile(`(?i)` + regexp.QuoteMeta(term.SourceText))
				result = re.ReplaceAllString(result, term.TargetText)
			}
		}
	}
	return result
}

// restoreRegions restores protected regions
func restoreRegions(text string, regions []ProtectedRegion) string {
	result := text
	// Restore in reverse order to maintain indices
	for i := len(regions) - 1; i >= 0; i-- {
		region := regions[i]
		result = strings.ReplaceAll(result, region.Placeholder, region.Content)
	}
	return result
}

// buildCacheKey builds a cache key from content and request
func buildCacheKey(content string, req *TextTranslateRequest) string {
	glossaryID := ""
	if req.Glossary != nil {
		glossaryID = req.Glossary.ProjectID
	}
	key := fmt.Sprintf("%s:%s:%s:%s", content, req.SourceLang, req.TargetLang, glossaryID)
	hash := sha256.Sum256([]byte(key))
	return hex.EncodeToString(hash[:])
}

// findGlossaryHits finds glossary term hits in text
func findGlossaryHits(text string, glossary Glossary) []TermHit {
	var hits []TermHit
	for _, term := range glossary.Terms {
		pos := strings.Index(text, term.SourceText)
		if pos != -1 {
			hits = append(hits, TermHit{
				Source:   term.SourceText,
				Target:   term.TargetText,
				Position: pos,
			})
		}
	}
	return hits
}

// generateTraceID generates a trace ID
func generateTraceID() string {
	hash := sha256.Sum256([]byte(fmt.Sprintf("%d", time.Now().UnixNano())))
	return hex.EncodeToString(hash[:])[:16]
}

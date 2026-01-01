package translation

import (
	"bytes"
	"context"
	"fmt"
	"image"
	"image/jpeg"
	"image/png"
	"strings"
)

// ImageTranslateRequest represents an image translation request
type ImageTranslateRequest struct {
	ImageBytes  []byte
	SourceLang  string
	TargetLang  string
	Mode        string // text_only, structured, overlay
	Domain      string
	Style       Style
	Glossary    *Glossary
}

// ImageTranslateResponse represents an image translation response
type ImageTranslateResponse struct {
	Blocks            []TranslatedBlock `json:"blocks"`
	FullTextTranslation string           `json:"full_text_translation"`
	Quality           *QualityReport     `json:"quality,omitempty"`
	TraceID           string             `json:"trace_id"`
}

// TranslatedBlock represents a translated block with bbox
type TranslatedBlock struct {
	Type           string  `json:"type"` // paragraph, caption, equation, table
	BBox           []int   `json:"bbox"` // [x, y, width, height]
	SourceText     string  `json:"source_text"`
	TranslatedText string  `json:"translated_text"`
}

// OCRBlock represents an OCR detected block
type OCRBlock struct {
	Type   string
	BBox   []int
	Text   string
	Confidence float64
}

// OCRClient interface for OCR operations
type OCRClient interface {
	DetectLayout(ctx context.Context, imageBytes []byte) ([]OCRBlock, error)
}

// ImageTranslator handles image translation
type ImageTranslator struct {
	ocrClient     OCRClient
	textTranslator *TextTranslator
	qualitySvc    QualityService
}

// NewImageTranslator creates a new image translator
func NewImageTranslator(ocrClient OCRClient, textTranslator *TextTranslator, qualitySvc QualityService) *ImageTranslator {
	return &ImageTranslator{
		ocrClient:     ocrClient,
		textTranslator: textTranslator,
		qualitySvc:    qualitySvc,
	}
}

// Translate performs image translation
func (t *ImageTranslator) Translate(ctx context.Context, req *ImageTranslateRequest) (*ImageTranslateResponse, error) {
	// 1. Preprocess image
	processed, err := preprocessImage(req.ImageBytes)
	if err != nil {
		return nil, fmt.Errorf("image preprocessing failed: %w", err)
	}

	// 2. OCR + Layout detection
	blocks, err := t.ocrClient.DetectLayout(ctx, processed)
	if err != nil {
		return nil, fmt.Errorf("OCR failed: %w", err)
	}

	// 3. Classify blocks
	classified := classifyBlocks(blocks)

	// 4. Merge context blocks
	merged := mergeContextBlocks(classified)

	// 5. Translate blocks
	translated := make([]TranslatedBlock, 0)
	for _, block := range merged {
		if block.Type == "equation" {
			// Equation: keep as-is or convert to LaTeX
			translated = append(translated, TranslatedBlock{
				Type:           "equation",
				BBox:           block.BBox,
				SourceText:     block.Text,
				TranslatedText: block.Text, // Keep original
			})
		} else if block.Type == "table" {
			// Table: structured translation
			tableTranslated := t.translateTable(ctx, block, req)
			translated = append(translated, tableTranslated)
		} else {
			// Normal text translation
			textReq := &TextTranslateRequest{
				SourceLang:  req.SourceLang,
				TargetLang:  req.TargetLang,
				Content:     block.Text,
				ContentType: "plain",
				Style:       req.Style,
				Glossary:    req.Glossary,
			}
			result, err := t.textTranslator.Translate(ctx, textReq)
			if err != nil {
				// Fallback: keep original text
				translated = append(translated, TranslatedBlock{
					Type:           block.Type,
					BBox:           block.BBox,
					SourceText:     block.Text,
					TranslatedText: block.Text,
				})
				continue
			}
			translated = append(translated, TranslatedBlock{
				Type:           block.Type,
				BBox:           block.BBox,
				SourceText:     block.Text,
				TranslatedText: result.Translation,
			})
		}
	}

	// 6. Build full text translation
	fullText := buildFullText(translated)

	// 7. Quality assessment
	quality := t.qualitySvc.AssessImage(ctx, blocks, translated)

	return &ImageTranslateResponse{
		Blocks:             translated,
		FullTextTranslation: fullText,
		Quality:            quality,
		TraceID:            generateTraceID(),
	}, nil
}

// preprocessImage preprocesses image (resize, denoise, rotation correction)
func preprocessImage(imageBytes []byte) ([]byte, error) {
	// Basic validation
	img, format, err := image.Decode(bytes.NewReader(imageBytes))
	if err != nil {
		return nil, err
	}

	// Limit resolution (max 2000px on longest side)
	bounds := img.Bounds()
	maxDim := 2000
	if bounds.Dx() > maxDim || bounds.Dy() > maxDim {
		// Resize logic would go here
		// For now, just return original
	}

	// Re-encode
	var buf bytes.Buffer
	switch format {
	case "png":
		if err := png.Encode(&buf, img); err != nil {
			return nil, err
		}
	case "jpeg", "jpg":
		if err := jpeg.Encode(&buf, img, nil); err != nil {
			return nil, err
		}
	default:
		return imageBytes, nil
	}

	return buf.Bytes(), nil
}

// classifyBlocks classifies blocks by type
func classifyBlocks(blocks []OCRBlock) []OCRBlock {
	classified := make([]OCRBlock, len(blocks))
	for i, block := range blocks {
		classified[i] = block
		// Simple classification based on text patterns
		if strings.Contains(block.Text, "=") || strings.Contains(block.Text, "\\") {
			classified[i].Type = "equation"
		} else if strings.Contains(block.Text, "|") || strings.Contains(block.Text, "\t") {
			classified[i].Type = "table"
		} else if strings.HasPrefix(strings.ToLower(block.Text), "figure") || strings.HasPrefix(strings.ToLower(block.Text), "图") {
			classified[i].Type = "caption"
		} else {
			classified[i].Type = "paragraph"
		}
	}
	return classified
}

// mergeContextBlocks merges blocks from the same paragraph
func mergeContextBlocks(blocks []OCRBlock) []OCRBlock {
	if len(blocks) == 0 {
		return blocks
	}

	merged := []OCRBlock{blocks[0]}
	for i := 1; i < len(blocks); i++ {
		last := &merged[len(merged)-1]
		current := blocks[i]

		// Merge if same type and close vertically
		if last.Type == current.Type && areCloseVertically(last.BBox, current.BBox) {
			last.Text += " " + current.Text
			// Update bbox to encompass both
			last.BBox = mergeBBox(last.BBox, current.BBox)
		} else {
			merged = append(merged, current)
		}
	}

	return merged
}

// areCloseVertically checks if two bboxes are close vertically
func areCloseVertically(bbox1, bbox2 []int) bool {
	if len(bbox1) < 4 || len(bbox2) < 4 {
		return false
	}
	y1 := bbox1[1]
	h1 := bbox1[3]
	y2 := bbox2[1]
	threshold := h1 / 2
	return abs(y2-y1-h1) < threshold
}

// mergeBBox merges two bounding boxes
func mergeBBox(bbox1, bbox2 []int) []int {
	if len(bbox1) < 4 || len(bbox2) < 4 {
		return bbox1
	}
	x1 := min(bbox1[0], bbox2[0])
	y1 := min(bbox1[1], bbox2[1])
	x2 := max(bbox1[0]+bbox1[2], bbox2[0]+bbox2[2])
	y2 := max(bbox1[1]+bbox1[3], bbox2[1]+bbox2[3])
	return []int{x1, y1, x2 - x1, y2 - y1}
}

// translateTable translates a table block
func (t *ImageTranslator) translateTable(ctx context.Context, block OCRBlock, req *ImageTranslateRequest) TranslatedBlock {
	// Simple table translation: split by lines and translate each cell
	lines := strings.Split(block.Text, "\n")
	translatedLines := make([]string, len(lines))

	for i, line := range lines {
		cells := strings.Split(line, "\t")
		translatedCells := make([]string, len(cells))
		for j, cell := range cells {
			textReq := &TextTranslateRequest{
				SourceLang:  req.SourceLang,
				TargetLang:  req.TargetLang,
				Content:     strings.TrimSpace(cell),
				ContentType: "plain",
				Style:       req.Style,
				Glossary:    req.Glossary,
			}
			result, err := t.textTranslator.Translate(ctx, textReq)
			if err == nil {
				translatedCells[j] = result.Translation
			} else {
				translatedCells[j] = cell
			}
		}
		translatedLines[i] = strings.Join(translatedCells, "\t")
	}

	return TranslatedBlock{
		Type:           "table",
		BBox:           block.BBox,
		SourceText:     block.Text,
		TranslatedText: strings.Join(translatedLines, "\n"),
	}
}

// buildFullText builds full text from translated blocks
func buildFullText(blocks []TranslatedBlock) string {
	var parts []string
	for _, block := range blocks {
		if block.Type != "equation" {
			parts = append(parts, block.TranslatedText)
		}
	}
	return strings.Join(parts, "\n\n")
}

// Helper functions
func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

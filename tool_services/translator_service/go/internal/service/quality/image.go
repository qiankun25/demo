package quality

import (
	"context"
	"strings"

	"github.com/demo-feature-nexus/translator-service/internal/service/translation"
)

// AssessImage performs quality assessment for image translation
func (s *qualityService) AssessImage(ctx context.Context, blocks []translation.OCRBlock, translated []translation.TranslatedBlock) *translation.QualityReport {
	report := &translation.QualityReport{
		Score:             0.8,
		Issues:            []string{},
		GlossaryHitRate:   0.0,
		NumberConsistency: true,
	}

	// Check OCR confidence
	avgConfidence := 0.0
	for _, block := range blocks {
		avgConfidence += block.Confidence
	}
	if len(blocks) > 0 {
		avgConfidence /= float64(len(blocks))
		if avgConfidence < 0.7 {
			report.Issues = append(report.Issues, "low_ocr_confidence")
		}
	}

	// Check table structure preservation
	for _, block := range translated {
		if block.Type == "table" {
			sourceCells := countTableCells(block.SourceText)
			targetCells := countTableCells(block.TranslatedText)
			if sourceCells != targetCells {
				report.Issues = append(report.Issues, "table_structure_uncertain")
			}
		}
	}

	// Calculate score
	score := 0.8
	if avgConfidence > 0.8 {
		score += 0.1
	}
	if len(report.Issues) == 0 {
		score = 1.0
	}
	report.Score = score

	return report
}

// countTableCells counts cells in a table text
func countTableCells(text string) int {
	lines := strings.Split(text, "\n")
	if len(lines) == 0 {
		return 0
	}
	// Count cells in first line
	cells := strings.Split(lines[0], "\t")
	return len(cells) * len(lines)
}


package quality

import (
	"context"
	"regexp"
	"strings"

	"github.com/demo-feature-nexus/translator-service/internal/service/translation"
)

// QualityService provides quality assessment
type QualityService interface {
	Assess(ctx context.Context, source, target string, glossary translation.Glossary) *translation.QualityReport
}

type qualityService struct{}

// NewQualityService creates a new quality service
func NewQualityService() QualityService {
	return &qualityService{}
}

// Assess performs quality assessment
func (s *qualityService) Assess(ctx context.Context, source, target string, glossary translation.Glossary) *translation.QualityReport {
	report := &translation.QualityReport{
		Score:             0.8, // Default score
		Issues:            []string{},
		GlossaryHitRate:   0.0,
		NumberConsistency: true,
	}

	// Check glossary hit rate
	if len(glossary.Terms) > 0 {
		hits := 0
		for _, term := range glossary.Terms {
			if strings.Contains(target, term.TargetText) {
				hits++
			}
		}
		report.GlossaryHitRate = float64(hits) / float64(len(glossary.Terms))
		if report.GlossaryHitRate < 0.5 {
			report.Issues = append(report.Issues, "low_glossary_hit_rate")
		}
	}

	// Check number consistency
	numbersSource := extractNumbers(source)
	numbersTarget := extractNumbers(target)
	if !compareNumbers(numbersSource, numbersTarget) {
		report.NumberConsistency = false
		report.Issues = append(report.Issues, "number_inconsistency")
	}

	// Calculate overall score
	score := 0.8
	if report.GlossaryHitRate > 0.8 {
		score += 0.1
	}
	if report.NumberConsistency {
		score += 0.1
	}
	if len(report.Issues) == 0 {
		score = 1.0
	}
	report.Score = score

	return report
}

// extractNumbers extracts numbers from text
func extractNumbers(text string) []string {
	re := regexp.MustCompile(`\d+\.?\d*`)
	return re.FindAllString(text, -1)
}

// compareNumbers compares number lists
func compareNumbers(source, target []string) bool {
	if len(source) != len(target) {
		return false
	}
	for i, s := range source {
		if i >= len(target) || s != target[i] {
			return false
		}
	}
	return true
}


package translation

import (
	"context"
	"strings"
	"testing"
	"time"
)

// Mock implementations for testing
type mockEngine struct{}

func (m *mockEngine) Translate(ctx context.Context, req *TranslateRequest) (string, error) {
	return "Translated: " + req.Text, nil
}

func (m *mockEngine) PostEdit(ctx context.Context, draft string, glossary Glossary, style Style) (string, error) {
	return draft, nil
}

type mockGlossaryService struct{}

func (m *mockGlossaryService) LoadGlossary(ctx context.Context, projectID string) (Glossary, error) {
	return Glossary{
		ProjectID: projectID,
		Terms: []Term{
			{SourceText: "test", TargetText: "测试"},
		},
	}, nil
}

type mockQualityService struct{}

func (m *mockQualityService) Assess(ctx context.Context, source, target string, glossary Glossary) *QualityReport {
	return &QualityReport{
		Score:             0.9,
		Issues:            []string{},
		GlossaryHitRate:   1.0,
		NumberConsistency: true,
	}
}

type mockCache struct{}

func (m *mockCache) Get(ctx context.Context, key string) interface{} {
	return nil
}

func (m *mockCache) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	return nil
}

func TestTextTranslator_Translate(t *testing.T) {
	translator := NewTextTranslator(
		&mockEngine{},
		&mockGlossaryService{},
		&mockQualityService{},
		&mockCache{},
	)

	req := &TextTranslateRequest{
		SourceLang:  "en",
		TargetLang:  "zh",
		Content:     "Hello world",
		ContentType: "plain",
		Options: struct {
			ReturnAlignment bool `json:"return_alignment"`
			ReturnQuality   bool `json:"return_quality"`
		}{
			ReturnQuality: true,
		},
	}

	result, err := translator.Translate(context.Background(), req)
	if err != nil {
		t.Fatalf("Translation failed: %v", err)
	}

	if result.Translation == "" {
		t.Error("Translation result is empty")
	}

	if result.Quality == nil {
		t.Error("Quality report is missing")
	}
}

func TestNormalizeText(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"Hello　world", "Hello world"},
		{"  multiple   spaces  ", "multiple spaces"},
		{"normal text", "normal text"},
	}

	for _, tt := range tests {
		result := normalizeText(tt.input)
		if result != tt.expected {
			t.Errorf("normalizeText(%q) = %q, want %q", tt.input, result, tt.expected)
		}
	}
}

func TestProtectRegions(t *testing.T) {
	segments := []string{
		"Text with $latex$ formula",
		"Code: ```python\nprint('hello')\n```",
	}

	protected, regions := protectRegions(segments)

	if len(regions) == 0 {
		t.Error("No protected regions found")
	}

	// Check that placeholders are in protected text
	hasPlaceholder := false
	for _, region := range regions {
		if contains(protected, region.Placeholder) {
			hasPlaceholder = true
			break
		}
	}

	if !hasPlaceholder {
		t.Error("Protected text should contain placeholders")
	}
}

func contains(s, substr string) bool {
	return strings.Contains(s, substr)
}


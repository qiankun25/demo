package translation

import (
	"context"
)

// Style represents translation style preferences
type Style struct {
	Tone            string `json:"tone"`            // formal, neutral
	Fidelity        string `json:"fidelity"`        // high, balanced, fluent
	PreserveCitations bool  `json:"preserve_citations"`
	PreserveLaTeX    bool  `json:"preserve_latex"`
}

// TranslateRequest represents a translation request
type TranslateRequest struct {
	SourceLang string `json:"source_lang"`
	TargetLang string `json:"target_lang"`
	Text       string `json:"text"`
	Style      Style  `json:"style"`
}

// TranslationEngine defines the interface for translation engines
type TranslationEngine interface {
	// Translate performs basic translation
	Translate(ctx context.Context, req *TranslateRequest) (string, error)
	
	// PostEdit performs post-editing with glossary and style rules
	PostEdit(ctx context.Context, draft string, glossary Glossary, style Style) (string, error)
}

// Glossary represents a glossary for terminology enforcement
type Glossary struct {
	ProjectID string
	Terms     []Term
}

// Term represents a glossary term
type Term struct {
	SourceText   string
	TargetText   string
	CaseSensitive bool
	RegexPattern  string
	Priority      int
}


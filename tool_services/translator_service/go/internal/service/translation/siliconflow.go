package translation

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// SiliconFlowEngine implements TranslationEngine using SiliconFlow API
type SiliconFlowEngine struct {
	apiKey  string
	apiBase string
	model   string
	client  *http.Client
}

// NewSiliconFlowEngine creates a new SiliconFlow engine
func NewSiliconFlowEngine(apiKey, apiBase, model string) *SiliconFlowEngine {
	return &SiliconFlowEngine{
		apiKey:  apiKey,
		apiBase: apiBase,
		model:   model,
		client: &http.Client{
			Timeout: 90 * time.Second,
		},
	}
}

// Translate implements TranslationEngine
func (e *SiliconFlowEngine) Translate(ctx context.Context, req *TranslateRequest) (string, error) {
	systemPrompt := fmt.Sprintf(
		"You are a professional multilingual translator.\n"+
			"Translate the given text from %s to %s.\n"+
			"Return ONLY the translated text.",
		req.SourceLang, req.TargetLang,
	)

	payload := map[string]interface{}{
		"model": e.model,
		"messages": []map[string]interface{}{
			{
				"role":    "system",
				"content": systemPrompt,
			},
			{
				"role":    "user",
				"content": req.Text,
			},
		},
		"max_tokens":  2000,
		"temperature": 0.2,
		"top_p":       0.9,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", e.apiBase, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Authorization", "Bearer "+e.apiKey)
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := e.client.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("API error: %d - %s", resp.StatusCode, string(body))
	}

	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	if len(result.Choices) == 0 {
		return "", fmt.Errorf("empty response from API")
	}

	return result.Choices[0].Message.Content, nil
}

// PostEdit implements TranslationEngine
func (e *SiliconFlowEngine) PostEdit(ctx context.Context, draft string, glossary Glossary, style Style) (string, error) {
	// Build glossary terms list
	termsList := ""
	for _, term := range glossary.Terms {
		termsList += fmt.Sprintf("- %s -> %s\n", term.SourceText, term.TargetText)
	}

	systemPrompt := fmt.Sprintf(
		"You are a professional academic translator post-editor.\n"+
			"Task: Refine the draft translation to ensure:\n"+
			"1. Terminology consistency (use these terms: %s)\n"+
			"2. Academic tone (%s)\n"+
			"3. Format preservation (citations: %v, LaTeX: %v)\n"+
			"Return ONLY the refined translation.",
		termsList, style.Tone, style.PreserveCitations, style.PreserveLaTeX,
	)

	payload := map[string]interface{}{
		"model": e.model,
		"messages": []map[string]interface{}{
			{
				"role":    "system",
				"content": systemPrompt,
			},
			{
				"role":    "user",
				"content": "Draft translation:\n" + draft,
			},
		},
		"max_tokens":  2000,
		"temperature": 0.3,
		"top_p":       0.9,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", e.apiBase, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Authorization", "Bearer "+e.apiKey)
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := e.client.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("API error: %d - %s", resp.StatusCode, string(body))
	}

	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	if len(result.Choices) == 0 {
		return draft, nil // Return draft if post-edit fails
	}

	return result.Choices[0].Message.Content, nil
}


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

// DashScopeEngine implements TranslationEngine using DashScope (Qwen) API
type DashScopeEngine struct {
	apiKey string
	model  string
	client *http.Client
}

// NewDashScopeEngine creates a new DashScope engine
func NewDashScopeEngine(apiKey, model string) *DashScopeEngine {
	return &DashScopeEngine{
		apiKey: apiKey,
		model:  model,
		client: &http.Client{
			Timeout: 90 * time.Second,
		},
	}
}

// Translate implements TranslationEngine
func (e *DashScopeEngine) Translate(ctx context.Context, req *TranslateRequest) (string, error) {
	prompt := fmt.Sprintf(
		"你是一个专业的学术翻译助手。\n"+
			"请将以下文本从 %s 翻译为 %s。\n"+
			"只返回翻译结果，不要添加解释或额外内容。\n\n"+
			"文本：\n%s",
		req.SourceLang, req.TargetLang, req.Text,
	)

	payload := map[string]interface{}{
		"model": e.model,
		"input": map[string]interface{}{
			"messages": []map[string]interface{}{
				{
					"role":    "user",
					"content": prompt,
				},
			},
		},
		"parameters": map[string]interface{}{
			"temperature": 0.3,
			"max_tokens":  2000,
		},
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation", bytes.NewBuffer(jsonData))
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
		Output struct {
			Choices []struct {
				Message struct {
					Content string `json:"content"`
				} `json:"message"`
			} `json:"choices"`
		} `json:"output"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	if len(result.Output.Choices) == 0 {
		return "", fmt.Errorf("empty response from API")
	}

	return result.Output.Choices[0].Message.Content, nil
}

// PostEdit implements TranslationEngine
func (e *DashScopeEngine) PostEdit(ctx context.Context, draft string, glossary Glossary, style Style) (string, error) {
	termsList := ""
	for _, term := range glossary.Terms {
		termsList += fmt.Sprintf("- %s -> %s\n", term.SourceText, term.TargetText)
	}

	prompt := fmt.Sprintf(
		"你是一个专业的学术翻译后编辑助手。\n"+
			"任务：优化以下草稿翻译，确保：\n"+
			"1. 术语一致性（使用这些术语：\n%s）\n"+
			"2. 学术语气（%s）\n"+
			"3. 格式保留（引用：%v，LaTeX：%v）\n"+
			"只返回优化后的翻译，不要添加解释。\n\n"+
			"草稿翻译：\n%s",
		termsList, style.Tone, style.PreserveCitations, style.PreserveLaTeX, draft,
	)

	payload := map[string]interface{}{
		"model": e.model,
		"input": map[string]interface{}{
			"messages": []map[string]interface{}{
				{
					"role":    "user",
					"content": prompt,
				},
			},
		},
		"parameters": map[string]interface{}{
			"temperature": 0.3,
			"max_tokens":  2000,
		},
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation", bytes.NewBuffer(jsonData))
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
		return draft, nil // Return draft if post-edit fails
	}

	var result struct {
		Output struct {
			Choices []struct {
				Message struct {
					Content string `json:"content"`
				} `json:"message"`
			} `json:"choices"`
		} `json:"output"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return draft, nil
	}

	if len(result.Output.Choices) == 0 {
		return draft, nil
	}

	return result.Output.Choices[0].Message.Content, nil
}


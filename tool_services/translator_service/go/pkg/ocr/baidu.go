package ocr

import (
	"bytes"
	"context"
	"crypto/md5"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"mime/multipart"
	"net/http"
	"time"

	"github.com/demo-feature-nexus/translator-service/internal/service/translation"
)

// BaiduOCRClient implements OCRClient using Baidu Image Translation API
type BaiduOCRClient struct {
	appID     string
	secretKey string
	client    *http.Client
}

// NewBaiduOCRClient creates a new Baidu OCR client
func NewBaiduOCRClient(appID, secretKey string) *BaiduOCRClient {
	return &BaiduOCRClient{
		appID:     appID,
		secretKey: secretKey,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// DetectLayout performs OCR and layout detection
func (c *BaiduOCRClient) DetectLayout(ctx context.Context, imageBytes []byte) ([]translation.OCRBlock, error) {
	// Check image size (max 2MB)
	if len(imageBytes) > 2*1024*1024 {
		return nil, fmt.Errorf("image size exceeds 2MB")
	}

	// Calculate MD5
	hash := md5.Sum(imageBytes)
	fileMD5 := fmt.Sprintf("%x", hash)

	// Generate salt
	salt := fmt.Sprintf("%d", rand.Intn(32768)+32768)

	// Generate sign
	signStr := c.appID + fileMD5 + salt + "APICUID" + "mac" + c.secretKey
	signHash := md5.Sum([]byte(signStr))
	sign := fmt.Sprintf("%x", signHash)

	// Prepare form data
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)

	// Add fields
	writer.WriteField("from", "en")
	writer.WriteField("to", "zh")
	writer.WriteField("appid", c.appID)
	writer.WriteField("salt", salt)
	writer.WriteField("sign", sign)
	writer.WriteField("cuid", "APICUID")
	writer.WriteField("mac", "mac")

	// Add file
	fileWriter, err := writer.CreateFormFile("image", "image.png")
	if err != nil {
		return nil, err
	}
	if _, err := io.Copy(fileWriter, bytes.NewReader(imageBytes)); err != nil {
		return nil, err
	}
	writer.Close()

	// Send request
	req, err := http.NewRequestWithContext(ctx, "POST", "https://fanyi-api.baidu.com/api/trans/sdk/picture", &buf)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error: %d - %s", resp.StatusCode, string(body))
	}

	var result struct {
		ErrorCode int    `json:"error_code"`
		ErrorMsg  string `json:"error_msg"`
		Data      struct {
			Content []struct {
				Src string `json:"src"`
				Dst string `json:"dst"`
			} `json:"content"`
		} `json:"data"`
		Result struct {
			Blocks []struct {
				SrcText string `json:"src_text"`
				DstText string `json:"dst_text"`
				BBox    []int  `json:"bbox"`
			} `json:"blocks"`
		} `json:"result"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	if result.ErrorCode != 0 && result.ErrorCode != 20000 {
		return nil, fmt.Errorf("Baidu API error: %d - %s", result.ErrorCode, result.ErrorMsg)
	}

	// Convert to OCRBlock format
	var blocks []translation.OCRBlock

	// Try data.content format first
	if len(result.Data.Content) > 0 {
		for _, item := range result.Data.Content {
			blocks = append(blocks, translation.OCRBlock{
				Type:        "paragraph",
				Text:        item.Src,
				Confidence:  0.9,
			})
		}
	} else if len(result.Result.Blocks) > 0 {
		// Try result.blocks format
		for _, block := range result.Result.Blocks {
			bbox := block.BBox
			if len(bbox) == 0 {
				bbox = []int{0, 0, 0, 0}
			}
			blocks = append(blocks, translation.OCRBlock{
				Type:        "paragraph",
				BBox:        bbox,
				Text:        block.SrcText,
				Confidence:  0.9,
			})
		}
	}

	return blocks, nil
}


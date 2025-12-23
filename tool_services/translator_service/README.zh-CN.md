### translator_service（多模态翻译）

该服务用于将 **文本 + 图片** 输入翻译到目标语言，并将结果写入 MinIO（Claim Check）。

#### 输入（MockStorage 中的 key 对应 payload）

```json
{
  "text": "原文内容",
  "images": ["/tmp/a.png", "https://example.com/b.jpg"],
  "target_lang": "zh"
}
```

#### 输出（写入 `data:translate:{input_key}`）

```json
{
  "text_translated": "...",
  "images_translated": [
    {
      "input": "/tmp/a.png",
      "caption": "...",
      "extracted_text": "...",
      "translated_text": "..."
    }
  ],
  "meta": {
    "target_lang": "zh",
    "image_count": 1,
    "model": "..."
  }
}
```

#### 环境变量

- `SILICONFLOW_API_KEY`：必填
- `SILICONFLOW_API_BASE`：默认 `https://api.siliconflow.cn/v1/chat/completions`
- `SILICONFLOW_VISION_MODEL`：建议设置为**支持图像输入**的模型名；未设置时回退 `SILICONFLOW_MODEL`
- `TRANSLATE_MAX_TOKENS` / `TRANSLATE_TEMPERATURE` / `TRANSLATE_TOP_P`：生成参数

#### 本地自测

需要 MinIO 正常可用（MockStorage 后端）并设置 `SILICONFLOW_API_KEY`：

```bash
python3 tool_services/translator_service/nexus_tool/test_translator_local.py
```


# PDF 论文解析服务（TextRank，标准化产物）

基于 Gin 的轻量级 Web 应用：上传 PDF 后在本地提取文本，并用 **TextRank** 生成 **Summary + Keywords**（无需 GROBID、无需 LLM）。

本服务的输出已升级为**可索引的标准产物（3 件套）**：

1) **Doc（文档元数据）**
- `doc_id`（内部唯一）
- `canonical_id`（doi/arxiv，尽力从文件名/文本推断或由上游传入）
- `title/authors/year/venue`（启发式抽取或由上游传入）
- `source/license/open_access`
- `pdf_object_key`（MinIO 路径，由上游传入）
- `pdf_sha256`

2) **Chunks（可检索分片）**
- `chunk_id/doc_id`
- `text`（清洗后的段落/句子）
- `span`（当前实现为 `paragraph` 序号；后续可扩展页码）
- `section_path`（启发式标题路径）

3) **Summary/Keywords**
- `summary` + `summary_source`（`abstract_from_pdf` / `generated_summary`）
- `keywords`

## 功能
- `POST /api/convert`：接收 PDF，返回标准产物：
  - `doc`
  - `chunks[]`
  - `summary_keywords`
- `/`：静态页面，支持上传 PDF、展示 summary/keywords/text。

## 环境准备
- Go 1.21+

本服务不依赖任何外部模型或 GROBID。
为了在更多真实世界 PDF 上稳定提取文本，服务会优先使用纯 Go 解析器；若解析失败，会尝试调用本机 `pdftotext`（Poppler）。

### 可选依赖：pdftotext（推荐安装）
- macOS（Homebrew）：
  - `brew install poppler`
- Linux（Debian/Ubuntu）：
  - `sudo apt-get install -y poppler-utils`

如 `pdftotext` 不在 PATH，可通过环境变量指定：
- `PDFTOTEXT_BIN=/full/path/to/pdftotext`

## 启动步骤
```bash
go build ./...
go run main.go
```
默认监听 `:3000`，浏览器访问 `http://localhost:3000/`。

### 可配置环境变量
| 变量 | 说明 | 默认值 |
| ---- | ---- | ------ |
| `LISTEN_ADDR` | HTTP 监听地址 | `:3000` |
| `PDFTOTEXT_BIN` | pdftotext 可执行文件路径（可选） | `pdftotext` |


## API 示例
```bash
curl -X POST "http://localhost:3000/api/convert" \
     -F "file=@paper.pdf"
```
响应 JSON：
```json
{
  "doc": {
    "doc_id": "...",
    "canonical_id": "arxiv:1706.03762",
    "pdf_object_key": "task_id/xxx.pdf",
    "pdf_sha256": "..."
  },
  "chunks": [
    { "chunk_id": "...", "doc_id": "...", "text": "...", "span": { "paragraph": 1 }, "section_path": "3 Method" }
  ],
  "summary_keywords": {
    "summary": "...",
    "summary_source": "abstract_from_pdf",
    "keywords": ["...", "..."]
  }
}
```

## 前端页面
- `web/index.html` 随 Gin 一并提供，上传文件后会显示两块文本区域：
  - Summary/Keywords
  - 提取的纯文本（用于调试/校验）



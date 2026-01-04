# Image Translation API 快速参考

## 📍 接口端点

```
POST /api/v1/translate/image
```

## 📤 请求格式

### Content-Type
```
multipart/form-data
```

### 请求参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `file` | File | ✅ | 图片文件（PNG/JPG/WebP），最大 2MB |

**注意**: 当前实现中，语言参数（source_lang, target_lang）固定为 en -> zh，即使传递也会被忽略。

## 📥 响应格式

### 成功响应 (200 OK)

```json
{
  "status": "success",
  "service": "image-translation",
  "result": {
    "data": {
      "content": [
        {
          "src": "原文内容",
          "dst": "翻译后的内容"
        }
      ]
    }
  }
}
```

### 错误响应示例

#### 400 - 图片为空
```json
{
  "detail": "图片内容为空"
}
```

#### 500 - 翻译失败
```json
{
  "detail": "翻译失败: UNAUTHORIZED USER"
}
```

## 💻 使用示例

### cURL
```bash
curl -X POST http://localhost:8002/api/v1/translate/image \
  -F "file=@image.png"
```

### Python
```python
import requests

url = "http://localhost:8002/api/v1/translate/image"

with open("image.png", "rb") as f:
    files = {"file": ("image.png", f, "image/png")}
    response = requests.post(url, files=files)
    print(response.json())
```

### JavaScript
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://localhost:8002/api/v1/translate/image', {
  method: 'POST',
  body: formData
})
.then(res => res.json())
.then(data => console.log(data));
```

## 🔧 配置要求

需要设置以下环境变量（用于百度翻译 API）：

```bash
BAIDU_APP_ID=your_app_id
BAIDU_SECRET_KEY=your_secret_key
```

## 📚 API 文档

- **Swagger UI**: http://localhost:8002/docs
- **ReDoc**: http://localhost:8002/redoc
- **OpenAPI JSON**: http://localhost:8002/openapi.json


# Image Translation API 接口详细说明

## 接口端点

**POST** `/api/v1/translate/image`

## 请求格式

### Content-Type
```
multipart/form-data
```

### 请求参数

| 参数名 | 类型 | 必需 | 说明 | 默认值 |
|--------|------|------|------|--------|
| `file` | File | ✅ 是 | 图片文件（PNG/JPG/WebP），最大 2MB | - |
| `source_lang` | String | ❌ 否 | 源语言代码（当前实现中固定为 "en"） | "en" |
| `target_lang` | String | ❌ 否 | 目标语言代码（当前实现中固定为 "zh"） | "zh" |
| `mode` | String | ❌ 否 | 输出模式（文档中提及，但当前实现未支持） | - |
| `domain` | String | ❌ 否 | 领域上下文（文档中提及，但当前实现未支持） | - |

### 当前实现状态

⚠️ **注意**：当前代码实现中，接口只接受 `file` 参数。`source_lang` 和 `target_lang` 在代码中硬编码为 "en" -> "zh"。

## 响应格式

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

### 错误响应

#### 400 Bad Request - 图片为空
```json
{
  "detail": "图片内容为空"
}
```

#### 500 Internal Server Error - 翻译失败
```json
{
  "detail": "翻译失败: [错误信息]"
}
```

#### 错误码说明（来自百度 API）
- `52006`: 图片大小超过 2MB
- `-1`: 请求失败（网络错误等）

## 实际代码实现

### 接口定义（router.py）
```python
@router.post("/api/v1/translate/image", response_model=ImageTranslateResponse, tags=["Translation"])
async def translate_image_api(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片内容为空")

    result = translate_image_bytes(content)
    if result.get("error_code") not in (0, "0", None):
        error_msg = result.get("error_msg", "未知错误")
        logger.error("百度图片翻译错误: %s", error_msg)
        raise HTTPException(status_code=500, detail=f"翻译失败: {error_msg}")

    return {
        "status": "success",
        "service": "image-translation",
        "result": result.get("result") or result.get("data") or result,
    }
```

### 核心翻译函数（image_translate.py）
```python
def translate_image_bytes(content: bytes) -> Dict[str, Any]:
    # 1. 检查图片大小（<= 2MB）
    if len(content) > 2 * 1024 * 1024:
        return {"error_code": 52006, "error_msg": "图片大小超过2MB"}

    # 2. 计算图片的 MD5（用于签名）
    file_md5 = get_file_md5(content)
    
    # 3. 生成随机 salt
    salt = str(random.randint(32768, 65536))
    
    # 4. 生成签名
    sign_str = settings.BAIDU_APP_ID + file_md5 + salt + CUID + MAC + settings.BAIDU_SECRET_KEY
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    # 5. 构建请求参数（固定 en -> zh）
    params = {
        'from': 'en',      
        'to': 'zh',        
        'appid': settings.BAIDU_APP_ID,
        'salt': salt,
        'sign': sign,
        'cuid': CUID,
        'mac': MAC
    }

    # 6. 发送请求到百度翻译 API
    files = {'image': ('image.png', content, 'application/octet-stream')}
    url = "https://fanyi-api.baidu.com/api/trans/sdk/picture"
    response = requests.post(url, params=params, files=files)
    return response.json()
```

## 使用示例

### cURL 命令

```bash
# 基本用法
curl -X POST http://localhost:8002/api/v1/translate/image \
  -F "file=@/path/to/image.png"

# 指定语言（当前实现中会被忽略，但可以传递）
curl -X POST http://localhost:8002/api/v1/translate/image \
  -F "file=@image.png" \
  -F "source_lang=en" \
  -F "target_lang=zh"
```

### Python 示例

```python
import requests

url = "http://localhost:8002/api/v1/translate/image"

# 方式1: 使用文件路径
with open("image.png", "rb") as f:
    files = {"file": ("image.png", f, "image/png")}
    response = requests.post(url, files=files)

# 方式2: 使用字节数据
with open("image.png", "rb") as f:
    image_bytes = f.read()
    files = {"file": ("image.png", image_bytes, "image/png")}
    response = requests.post(url, files=files)

print(response.json())
```

### JavaScript/Fetch 示例

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://localhost:8002/api/v1/translate/image', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

## 数据模型

### ImageTranslateResponse (Pydantic Model)

```python
class ImageBlock(BaseModel):
    src_text: str = Field(..., description="图片中识别出的原文")
    dst_text: str = Field(..., description="翻译后的文本")
    confidence: Optional[float] = Field(None, description="识别置信度")

class ImageTranslateResult(BaseModel):
    blocks: List[ImageBlock] = Field(default_factory=list, description="图片中的文本块翻译结果")
    full_text: Optional[str] = Field(None, description="合并后的完整译文")

class ImageTranslateResponse(BaseModel):
    status: str = Field("success", description="请求状态")
    service: str = Field("image-translation", description="服务名称")
    result: ImageTranslateResult
```

## 依赖服务

### 百度翻译 API
- **需要配置**: `BAIDU_APP_ID` 和 `BAIDU_SECRET_KEY`
- **API 端点**: `https://fanyi-api.baidu.com/api/trans/sdk/picture`
- **限制**: 图片大小 ≤ 2MB

### 环境变量配置

```bash
# 必需（用于图片 OCR 翻译）
BAIDU_APP_ID=your_app_id
BAIDU_SECRET_KEY=your_secret_key

# 可选（用于文本翻译和多模态）
SILICONFLOW_API_KEY=your_key
```

## 注意事项

1. **图片格式**: 支持 PNG、JPG、WebP 等常见格式
2. **文件大小**: 最大 2MB，超过会返回错误
3. **语言支持**: 当前实现固定为英文到中文（en -> zh）
4. **API 密钥**: 需要配置百度翻译 API 的 App ID 和 Secret Key
5. **异步处理**: 当前接口是同步的，大图片可能需要等待较长时间

## API 文档访问

服务启动后，可以通过以下地址访问交互式 API 文档：

- **Swagger UI**: http://localhost:8002/docs
- **ReDoc**: http://localhost:8002/redoc
- **OpenAPI JSON**: http://localhost:8002/openapi.json

## 测试示例

### 创建测试图片

```python
from PIL import Image
import io

# 创建一个简单的测试图片
img = Image.new('RGB', (200, 100), color='white')
img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# 发送请求
files = {"file": ("test.png", img_bytes, "image/png")}
response = requests.post("http://localhost:8002/api/v1/translate/image", files=files)
print(response.json())
```


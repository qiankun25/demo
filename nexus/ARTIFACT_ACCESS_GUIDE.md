# Nexus Artifact 访问详细指南

## 一、Storage Key 访问机制详解

### 1.1 三种 Artifact Key 类型

Nexus API 的 `/jobs/{trace_id}/artifacts/{artifact_key}` 端点支持三种类型的键：

#### 类型 1：逻辑键（Logical Key）
- **格式**：简单的字符串标识符，如 `"detailed_manifest"`, `"search_results"`
- **映射关系**：存储在 `JobContext.artifacts` 字典中，映射到实际的 storage_key
- **示例**：
  ```python
  # JobContext.artifacts = {
  #     "detailed_manifest": "data:manifest:bd45a9af-bd5b-45b8-b547-c3125d574bad",
  #     "search_results": "data:discovery:bd45a9af-bd5b-45b8-b547-c3125d574bad"
  # }
  
  # 使用逻辑键访问
  GET /api/v1/jobs/{trace_id}/artifacts/detailed_manifest
  ```

#### 类型 2：直接 Storage Key
- **格式**：以 `"data:"` 开头的完整存储键，如 `"data:parse:data:download:data:work:task:xxx:work:0"`
- **授权检查**：系统会验证该 storage_key 是否属于该任务
- **示例**：
  ```python
  # 从 Manifest 中获取的 parse_key 可以直接使用
  parse_key = "data:parse:data:download:data:work:task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:0"
  
  # URL 编码后访问（因为包含冒号等特殊字符）
  GET /api/v1/jobs/{trace_id}/artifacts/data%3Aparse%3Adata%3Adownload%3Adata%3Awork%3Atask%3A...
  ```

#### 类型 3：Fallback 逻辑键
- **格式**：某些特殊逻辑键，系统有预定义的映射规则
- **示例**：`"detailed_manifest"` 可以映射到 `"data:manifest:{trace_id}"`

### 1.2 Storage Key 授权检查机制

当使用直接的 storage_key 访问时，系统会执行以下安全检查（`_is_authorized_storage_key`）：

```python
def _is_authorized_storage_key(trace_id, task_type, storage_key, work_keys):
    # 1. 检查是否是 Manifest
    if storage_key == f"data:manifest:{trace_id}":
        return True
    
    # 2. 检查是否是 Discovery 结果
    if storage_key.startswith("data:discovery:") and trace_id in storage_key:
        return True
    
    # 3. 从 storage_key 中提取 work_key，检查是否属于该任务
    work_key = _extract_work_key(storage_key)  # 查找 "data:work:" 标记
    if work_key and work_key in work_keys:
        return True
    
    return False
```

**关键点**：
- `_extract_work_key` 使用 `rfind("data:work:")` 查找最后一个 `"data:work:"` 标记
- 对于 `"data:parse:data:download:data:work:task:xxx:work:0"`，会提取出 `"task:xxx:work:0"`
- 然后检查这个 work_key 是否在任务的 `work_keys` 列表中

### 1.3 实际 Manifest 示例解析

根据你提供的真实 Manifest 返回体：

```json
[
  {
    "work_key": "task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:0",
    "download_key": "data:download:data:work:task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:0",
    "parse_key": "data:parse:data:download:data:work:task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:0",
    "index_key": "data:index:data:parse:data:download:data:work:task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:0"
  },
  {
    "work_key": "task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:1",
    "download_key": "data:download:data:work:task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:1",
    "parse_key": "data:parse:data:download:data:work:task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:1",
    "index_key": "data:index:data:parse:data:download:data:work:task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:1"
  }
]
```

**Storage Key 层级结构**：
```
work_key (标识符)
    ↓
data:work:{work_key} (原始工作项数据)
    ↓
data:download:data:work:{work_key} (下载后的文件)
    ↓
data:parse:data:download:data:work:{work_key} (解析后的结构化数据)
    ↓
data:index:data:parse:data:download:data:work:{work_key} (索引后的向量数据)
```

## 二、使用示例代码

### 2.1 获取 Manifest

```python
import requests

trace_id = "bd45a9af-bd5b-45b8-b547-c3125d574bad"
base_url = "http://8.134.183.68:8000"

# 方式 1：通过状态 API 获取 manifest URL
status = requests.get(f"{base_url}/api/v1/jobs/{trace_id}").json()
manifest_url = status["artifacts"]["detailed_manifest"]  # 相对路径，如 "/api/v1/jobs/.../artifacts/detailed_manifest"

# 拼接完整 URL
if manifest_url.startswith("/"):
    full_url = f"{base_url}{manifest_url}"
else:
    full_url = manifest_url

# 获取 Manifest
manifest = requests.get(full_url).json()
print(f"Manifest 包含 {len(manifest)} 个工作项")
```

### 2.2 使用 Storage Key 获取数据

```python
import requests
import urllib.parse

trace_id = "bd45a9af-bd5b-45b8-b547-c3125d574bad"
base_url = "http://8.134.183.68:8000"

# 从 Manifest 中获取 parse_key
manifest = [...]  # 上面的 Manifest 数据
parse_key = manifest[0]["parse_key"]
# parse_key = "data:parse:data:download:data:work:task:bd45a9af-bd5b-45b8-b547-c3125d574bad:work:0"

# 重要：需要对 storage_key 进行 URL 编码（因为包含冒号等特殊字符）
encoded_key = urllib.parse.quote(parse_key, safe='')
# encoded_key = "data%3Aparse%3Adata%3Adownload%3Adata%3Awork%3Atask%3A..."

# 访问 API
url = f"{base_url}/api/v1/jobs/{trace_id}/artifacts/{encoded_key}"
response = requests.get(url)
response.raise_for_status()

# 解析数据（假设是 JSON）
parse_data = response.json()
print(f"论文标题: {parse_data.get('title')}")
print(f"摘要: {parse_data.get('llm_summary')}")
```

### 2.3 完整流程示例

```python
import requests
import urllib.parse
import time
import json

BASE_URL = "http://8.134.183.68:8000"
API_PREFIX = f"{BASE_URL}/api/v1"

# 1. 提交任务
response = requests.post(f"{API_PREFIX}/jobs", json={
    "task_type": "MORNING_REPORT",
    "parameters": {"limit": 5, "query": "LLM Agents"}
})
trace_id = response.json()["trace_id"]
print(f"任务已提交，trace_id: {trace_id}")

# 2. 等待完成
while True:
    status = requests.get(f"{API_PREFIX}/jobs/{trace_id}").json()
    print(f"状态: {status['status']}, 完成: {status['completed_count']}/{status['total_work_items']}")
    
    if status["status"] == "completed":
        break
    time.sleep(2)

# 3. 获取 Manifest（使用逻辑键）
manifest_url = status["artifacts"]["detailed_manifest"]
if manifest_url.startswith("/"):
    manifest_url = f"{BASE_URL}{manifest_url}"

manifest = requests.get(manifest_url).json()
print(f"\nManifest 包含 {len(manifest)} 个工作项")

# 4. 获取所有 parse 数据（使用 storage_key）
for item in manifest:
    work_key = item["work_key"]
    parse_key = item["parse_key"]  # 这是 storage_key
    
    # URL 编码 storage_key
    encoded_key = urllib.parse.quote(parse_key, safe='')
    
    # 获取数据
    url = f"{API_PREFIX}/jobs/{trace_id}/artifacts/{encoded_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        parse_data = response.json()
        
        print(f"\n工作项 {work_key}:")
        print(f"  标题: {parse_data.get('title', 'N/A')}")
        summary = parse_data.get('llm_summary', '')
        if summary:
            print(f"  摘要: {summary[:100]}...")
    except Exception as e:
        print(f"  获取失败: {e}")
```

## 三、关键注意事项

### 3.1 URL 编码的重要性

**为什么需要 URL 编码？**

Storage key 包含特殊字符（如冒号 `:`），在 URL 中有特殊含义。必须进行编码：

```python
# ❌ 错误：直接使用（会导致 URL 解析错误）
parse_key = "data:parse:data:work:task:xxx:work:0"
url = f"/api/v1/jobs/{trace_id}/artifacts/{parse_key}"

# ✅ 正确：URL 编码
encoded = urllib.parse.quote(parse_key, safe='')
url = f"/api/v1/jobs/{trace_id}/artifacts/{encoded}"
```

**Python `urllib.parse.quote` 参数说明**：
- `safe=''`：不保留任何字符（包括 `/`），所有特殊字符都编码
- 默认 `safe='/'`：保留斜杠，但这可能导致问题

### 3.2 Storage Key 的层级关系

Storage key 采用嵌套前缀的设计，体现了数据流转过程：

```
data:work:{work_key}                    # 原始工作项
  ↓
data:download:data:work:{work_key}      # 下载后
  ↓
data:parse:data:download:data:work:{work_key}  # 解析后
  ↓
data:index:data:parse:data:download:data:work:{work_key}  # 索引后
```

**好处**：
- 可以从任意层级的 key 追溯到原始 work_key
- `_extract_work_key` 通过查找 `"data:work:"` 标记来提取 work_key

### 3.3 授权检查的层级

系统按以下顺序检查授权：

1. **逻辑键映射**：先从 `context.artifacts` 查找
2. **Fallback 规则**：如 `"detailed_manifest"` → `"data:manifest:{trace_id}"`
3. **直接 Storage Key**：
   - 检查是否是 Manifest：`data:manifest:{trace_id}`
   - 检查是否是 Discovery：`data:discovery:*{trace_id}*`
   - 提取 work_key，检查是否在任务的 work_keys 列表中

### 3.4 错误处理

```python
try:
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        print(f"Artifact 不存在: {artifact_key}")
    else:
        print(f"HTTP 错误: {e.response.status_code}")
except requests.exceptions.RequestException as e:
    print(f"请求失败: {e}")
except json.JSONDecodeError as e:
    print(f"JSON 解析失败: {e}")
```

## 四、测试程序使用说明

运行测试程序：

```bash
# 安装依赖
pip install requests

# 运行完整测试（提交新任务）
python test_nexus_client.py

# 检查已有任务状态（传入 trace_id）
python test_nexus_client.py bd45a9af-bd5b-45b8-b547-c3125d574bad
```

测试程序会自动：
1. 健康检查
2. 提交任务
3. 轮询等待完成
4. 获取 Manifest
5. 使用 storage_key 获取所有数据
6. 显示结果摘要

## 五、总结

**核心要点**：

1. **Manifest 中的键都是 storage_key**，可以直接使用，但需要 URL 编码
2. **系统会自动进行授权检查**，确保只能访问属于该任务的数据
3. **逻辑键（如 "detailed_manifest"）和 storage_key 都支持**，系统会智能识别
4. **URL 编码是关键**，使用 `urllib.parse.quote(key, safe='')` 对 storage_key 进行编码

**推荐做法**：

```python
# 使用封装的客户端类（如 test_nexus_client.py 中的 NexusClient）
client = NexusClient("http://8.134.183.68:8000")

# 获取 Manifest
manifest = client.get_manifest(trace_id)

# 获取数据（客户端会自动处理 URL 编码）
for item in manifest:
    parse_data = client.get_parse_data(trace_id, item["parse_key"])
```

这样可以避免手动处理 URL 编码和错误处理的复杂性。


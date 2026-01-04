# Retrieval Service 配置说明

## 概述

Retrieval Service 现在使用统一的配置文件 `config.yaml` 来管理所有配置项，移除了代码中的硬编码值。

## 配置文件位置

默认配置文件位于服务根目录：`tool_services/retrieval_service/config.yaml`

可以通过环境变量 `RETRIEVAL_CONFIG_FILE` 指定自定义配置文件路径。

## 配置优先级

配置值的优先级（从高到低）：
1. 环境变量（以 `RETRIEVAL_` 前缀）
2. `config.yaml` 文件中的值
3. 代码中的默认值

## 主要配置项

### 服务配置 (`service`)
- `name`: 服务名称
- `host`: 服务监听地址
- `port`: 服务端口
- `version`: 服务版本
- `title`: API 标题
- `description`: API 描述

### 上游服务 (`upstreams`)
- `discovery_base_url`: 发现服务地址
- `download_base_url`: 下载服务地址
- `parser_base_url`: 解析服务地址
- `indexing_base_url`: 索引服务地址

### 数据库配置 (`database`)
- `db_path`: SQLite 数据库文件路径
- `index_db_path`: 索引数据库路径（可选，默认指向 `../indexing_service/index.db`）
- `sqlite_timeout`: SQLite 连接超时时间

### 检索策略 (`retrieval`)
- `local_first`: 是否优先本地检索
- `min_local_hits`: 本地命中不足时触发外部检索的最小数量
- `min_local_score`: 本地命中计数的相似度阈值
- `ingest_external_hits`: 是否将外部命中异步入库
- `local_scan_limit`: 本地扫描限制
- `semantic_search_k_multiplier`: 语义检索 k 值倍数
- `semantic_search_max_k`: 语义检索最大 k 值

### Worker 配置 (`worker`)
- `enabled`: 是否启用 worker
- `poll_interval`: Worker 轮询间隔
- `max_event_attempts`: 最大事件重试次数
- `retry_delay_base`: 重试延迟基数
- `retry_backoff_exponent`: 指数退避底数

### Chroma 配置 (`chroma`)
- `collection`: Chroma collection 名称
- `distance`: 距离度量（cosine/l2/ip）
- `embed_dim`: 嵌入维度
- `persist_dir`: 持久化目录（可选，默认指向 `../indexing_service/chroma_data`）

### 常量配置 (`constants`)

包含所有状态字符串、事件类型、API 路径等常量，这些值现在统一从配置文件读取，便于维护和修改。

## 使用示例

### 修改服务端口

编辑 `config.yaml`:
```yaml
service:
  port: 9000
```

或使用环境变量：
```bash
export RETRIEVAL_SERVICE_PORT=9000
```

### 修改上游服务地址

编辑 `config.yaml`:
```yaml
upstreams:
  indexing_base_url: "http://indexing-service:8020"
```

或使用环境变量：
```bash
export RETRIEVAL_INDEXING_BASE_URL="http://indexing-service:8020"
```

### 修改检索策略

编辑 `config.yaml`:
```yaml
retrieval:
  min_local_hits: 10
  min_local_score: 0.05
```

## 迁移说明

从旧版本迁移：
1. 所有环境变量仍然有效（以 `RETRIEVAL_` 前缀）
2. 新增的配置项可以通过 `config.yaml` 或环境变量设置
3. 代码中的硬编码值已移除，统一从配置文件读取

## 注意事项

1. 配置文件使用 YAML 格式，注意缩进
2. 环境变量优先级高于配置文件
3. 修改配置文件后需要重启服务才能生效
4. 某些配置项（如数据库路径）支持相对路径和绝对路径


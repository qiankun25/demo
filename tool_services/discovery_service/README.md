## discovery_service

学术资源发现服务：对外提供只读查询 API，并通过 MQ worker 消费 `cmd.discovery.start` 生成 `evt.discovery.*` 事件。

### HTTP API
- `GET /health`
- `GET /v1/results/{result_id}`
- `GET /v1/results/{result_id}/min_fields?limit=50`

启动（本地）：

```bash
cd tool_services/discovery_service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# DB（Postgres）
export DISCOVERY_DATABASE_URL="postgresql://discovery_user:discovery_pass@localhost:5434/discovery"

uvicorn app.main:app --host 0.0.0.0 --port 8032 --reload
```

### MQ Worker
- 入口：`python -m app.worker_main`
- 消费：`cmd.discovery.start`
- 发布：`evt.discovery.finished` / `evt.discovery.failed`

常用环境变量（节选）：
- `RABBITMQ_URL`
- `NEXUS_CMD_EXCHANGE` / `NEXUS_EVT_EXCHANGE`
- `DISCOVERY_CMD_ROUTING_KEY` / `DISCOVERY_CMD_QUEUE`
- `DISCOVERY_DATABASE_URL`

### 配置管理
所有环境变量都由 `tool_services/discovery_service/settings.py` 中的 `DiscoverySettings` 管理，API、worker 和 `nexus_tool` 统一通过 `settings` 实例读取配置。常用字段包括数据库/消息队列配置（`discovery_database_url`、`rabbitmq_url`、`nexus_*`）、OpenAlex 相关参数（`openalex_*`）、缓存/速率限制（`discovery_cache_*`, `openalex_*`）、以及 `LOG_LEVEL` / `NEXUS_PREFETCH` 等。无需修改代码即可通过环境变量调整行为。

### 依赖（建议）
- Postgres（结果索引 + inbox/outbox）
- RabbitMQ（命令/事件）
- Redis（可选：OpenAlex 查询缓存，见 `nexus_tool`）



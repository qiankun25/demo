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

### 依赖（建议）
- Postgres（结果索引 + inbox/outbox）
- RabbitMQ（命令/事件）
- Redis（可选：OpenAlex 查询缓存，见 `nexus_tool`）



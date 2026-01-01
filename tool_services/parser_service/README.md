## parser_service

PDF 解析服务：通过 MQ worker 消费 `cmd.parser.start`，从 `download_service` 获取文件并解析为 chunks，结果写入对象存储（claim-check），并在 DB 保存索引。

### HTTP API
- `GET /health`
- `GET /v1/parsed/{doc_id}`：只读获取解析结果（ref-only）

启动（本地）：

```bash
cd tool_services/parser_service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export PARSER_DATABASE_URL="postgresql://parser_user:parser_pass@localhost:5435/parser"
export PARSER_MINIO_ENDPOINT="localhost:9000"
export PARSER_MINIO_ACCESS_KEY="minioadmin"
export PARSER_MINIO_SECRET_KEY="minioadmin"
export PARSER_MINIO_BUCKET="papers"

uvicorn app.main:app --host 0.0.0.0 --port 8031 --reload
```

### MQ Worker
- 入口：`python app/mq_worker.py`（或容器内单独启动）
- 依赖：
  - RabbitMQ：命令/事件
  - download_service：获取 signed URL（用于下载 PDF bytes）
  - MinIO：写入解析结果

### 数据与迁移
- Alembic：`migrations/` + `alembic.ini`
- 建议把迁移作为独立 job 运行（不要在 API/worker 启动时自动建表）



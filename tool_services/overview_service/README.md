## overview_service

领域综述/聚合服务：对外提供只读 API，从对象存储（claim-check）读取 overview 报告。

### HTTP API
- `GET /health`
- `GET /v1/reports/{trace_id}`

启动（本地）：

```bash
cd tool_services/overview_service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8040 --reload
```

### Worker（生成报告）
本服务的报告生成逻辑位于 `nexus_tool/tool_service.py`（用于被编排层调用/或以 worker 方式运行）。

建议环境变量（节选）：
- `SILICONFLOW2_API_KEY` / `SILICONFLOW2_API_BASE` / `SILICONFLOW2_MODEL`（SUMMARY_REPORT 需要）



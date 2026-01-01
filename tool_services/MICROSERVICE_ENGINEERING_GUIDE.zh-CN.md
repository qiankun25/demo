## 目标：把当前“可运行的拆分服务”推进到“真正工程化的独立微服务”

你现在的 `tool_services/*_service` 已经具备微服务雏形（多为 FastAPI + Dockerfile；部分具备 DB migration / MQ worker / 测试 / 部署文档），但仍存在一些典型的“单体仓库耦合/工程化缺口”，会影响 **独立构建、独立发布、独立运维、可观测、可回滚**。

下面按 **P0（必须）/P1（建议）/P2（增强）** 给出一套工程化基线，并附带本仓库的差距清单。

---

## P0（必须）：独立微服务最小可上线基线

### 1) 可独立构建/发布（Build & Release）
- **单服务可独立产物**：每个服务都能只靠自身目录（或发布的依赖包）完成构建，不依赖“从 monorepo 根目录跑起来才行”的 `sys.path` 黑魔法。
- **依赖可复现**：
  - 至少提供 **锁版本机制**（`requirements.txt` 固定版本 + `pip-compile` 或 Poetry/uv lock）
  - CI 中固定 Python 版本、固定依赖分辨率
- **镜像标准**：
  - 非 root 用户运行（参考 `download_service/Dockerfile`）
  - `HEALTHCHECK`（容器级）
  - 分层缓存友好（先装依赖，再拷代码）

### 2) 配置与密钥（Config & Secrets）
- **所有密钥只允许环境变量/Secret Manager 注入**（仓库中不得出现真实 key）
- `pydantic-settings` 统一配置入口（例如 `app/config.py` / `app/core/config.py`），并提供：
  - `.env.example`（本地启动用）
  - 必填项校验（启动即失败，而不是运行到一半才报错）
- **环境变量命名一致**：建议统一 `SERVICE_` 前缀 + 语义清晰的字段名（例如 `PARSER_DATABASE_URL`、`INDEX_DB_URL`、`DISCOVERY_REDIS_URL`）

### 3) 运维可用（Runtime）
- **健康检查分层**：
  - `GET /health/live`：只证明进程活着（不探测外部依赖）
  - `GET /health/ready`：探测关键依赖（DB/MQ/对象存储/下游 HTTP）
  - `GET /health`：可返回综合信息（给人看/排障）
- **超时/重试/幂等**：
  - 所有下游 HTTP 调用必须设置超时（你们多数已做）
  - MQ 消费必须幂等（inbox/outbox 已在部分服务实现，建议统一到 `nexus_contracts`）
  - 失败重试要有退避与最大重试次数
- **优雅关闭**：
  - worker 处理 SIGTERM：停止拉新消息，等待 in-flight 任务收尾

### 4) 契约与边界（Contracts & Boundaries）
- **服务间只传 ref（claim-check）**：不要跨服务传 storage key / 共享 DB 表
- **契约包版本化**：`nexus_contracts` 要能作为独立包发布（否则天然耦合 monorepo）
- **API 版本化**：对外 HTTP 建议 `/v1/...`（部分服务已有，需统一）

---

## P1（建议）：工程化成熟度（可维护/可扩展）

### 1) 可观测性（Observability）
- 结构化日志（JSON），每条日志包含：
  - `trace_id`、`work_key`、`service`、`event`/`command`、`duration_ms`
- 指标（Prometheus `/metrics`）：
  - 请求耗时、错误率、队列积压、外部依赖失败率
- 分布式追踪（OpenTelemetry）：
  - HTTP client/server + MQ propagation（trace_id 对齐）

### 2) 测试与质量门禁
- 单元测试 + 最小集成测试（docker-compose 起依赖）
- `ruff/black/mypy`（或同等）统一 lint/format/typecheck
- CI：每个服务至少做到 `lint + tests + build image`

### 3) 本地开发体验
- 每个服务提供：
  - `Makefile`（`make dev/test/build/up/down`）
  - `docker-compose.yml`（包含依赖：DB/MQ/MinIO/Redis）
  - OpenAPI 导出（`openapi.json`）或通过 `/openapi.json` 获取

---

## P2（增强）：生产级鲁棒与治理
- API 网关与统一鉴权（JWT/API key/mTLS）
- 限流/配额、熔断、降级策略
- 数据迁移与回滚策略（Alembic + 版本化 schema）
- 灾备（备份、恢复、演练）
- 多环境发布（dev/staging/prod）+ 配置隔离

---

## 本仓库现状要点（你可以优先改这些）

### 已经做得比较像“独立微服务”的
- `download_service`：有较完整的 Dockerfile（非 root + HEALTHCHECK）、compose、测试、部署文档、health/ready/live。

### 共性不足（优先级从高到低）
- **monorepo 路径耦合**：多个服务通过 `sys.path` 注入来引用共享代码；建议逐步替换为“可安装/可发布的包”。
- **依赖不可复现**：不少服务 `requirements.txt` 使用 `>=` 或无版本，容易出现“今天能跑明天不能跑”。
- **健康检查不分层**：多数只有 `/health` 且不探测依赖，K8s/容器编排无法准确做 readiness。
- **缺少独立的本地启动栈**：除了 `download_service`，其它服务普遍缺少各自的 compose/Makefile/README（导致上手成本高）。
- **可观测性不统一**：日志格式、字段、trace 传播在不同服务里不一致。

---

## 服务级差距清单（简版）

- **discovery_service**
  - 现状：有 API + MQ worker + migrations + Dockerfile，但缺少完整 compose/README、健康检查偏弱、存在 monorepo 路径注入。
  - 建议：补齐 README/compose；/health/ready 探测 Postgres/RabbitMQ/Redis（可选）；统一用 `nexus_contracts` 的 command/event payload 模型。

- **parser_service**
  - 现状：有 MQ worker + migrations + Dockerfile；API/worker 仍有本地路径注入；缺少 compose/测试。
  - 建议：补齐 compose（Postgres/RabbitMQ/MinIO）；补单测（PDF parsing、idempotency）；增加 readiness（DB/MQ/MinIO）。

- **indexing_service**
  - 现状：API + MQ worker + migrations；依赖未锁；health 未分层；（历史上容易出现启动期小问题）。
  - 建议：锁依赖；增加 ready/live；将 Chroma/DB 初始化与错误处理做成可观测、可恢复的流程。

- **overview_service**
  - 现状：API 很薄（读 MockStorage）；缺少 README/compose；依赖/观测性较弱。
  - 建议：补齐 README/compose；增加对对象存储的 readiness；明确 worker 与 API 的部署拓扑。

- **translator_service**
  - 现状：功能丰富但需要外部 API；注意密钥管理与错误降级；建议拆分“旧接口兼容层”和“unified_backend”。
  - 建议：统一配置入口；对外 API 加 rate limit/鉴权；对外部 LLM/OCR 调用做超时/重试/熔断。

- **retrieval_service**
  - 现状：编排层 + 本地状态机（SQLite）；需要明确生产部署时的持久化与并发策略。
  - 建议：若要多实例：SQLite 要换 Postgres（或引入分布式锁/队列）；worker 与 API 分离部署；补齐可观测性与重试策略。



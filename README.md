### demo-main：事件驱动微服务 Demo（RabbitMQ + MinIO + Python）

本项目演示一个“编排中枢（Nexus）+ 多个工具微服务（Tool Services）”的事件驱动流水线。编排层只传 `key`，真实数据写入 MinIO（Claim Check 模式）。

---

### 目录结构（重点）

- `nexus_service/core.py`：编排中枢（监听事件，调度下一步）
- `shared/common.py` / `nexus_sdk/*`：消息协议、路由表、MockStorage(MinIO)
- `tool_services/*/nexus_tool/tool_service.py`：各工具微服务（Discovery/Downloader/Parser/Indexer/Overview/Translator/Retrieval）
- `run_demo.py`：本地一键启动 demo（启动多个服务 + 提交任务）
- `docker-compose.demo.yml`：本 demo 需要的容器（RabbitMQ + MinIO）

---

### 先决条件

- **Docker Desktop**（用于启动 RabbitMQ/MinIO）
- **Python 3.9+**

---

### 1) 启动依赖容器（RabbitMQ + MinIO）

在项目根目录执行：

```bash
docker compose -f docker-compose.demo.yml up -d
```

检查服务：
- RabbitMQ 管理台：`http://localhost:15672`（默认 `guest/guest`）
- MinIO Console：`http://localhost:9001`（默认 `minioadmin/minioadmin`）

停止容器：

```bash
docker compose -f docker-compose.demo.yml down
```

---

### 2) 配置 Python 环境

建议使用 venv：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-demo.txt
```

说明：`chromadb` 依赖较多（可能影响你本机其它 Python 包），建议在 venv 内安装。

---

### 3) 配置环境变量

#### 3.1 RabbitMQ（默认即可）

项目默认使用：
- `amqp://guest:guest@localhost:5672/`

如果你要改，请修改 `shared/common.py` / `nexus_sdk/common.py` 中的 `RabbitConfig.URL`。

#### 3.2 MinIO（MockStorage 后端）

默认（不配也能跑）：

```bash
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"
export MINIO_BUCKET="papers"
export MINIO_SECURE="false"
export NEXUS_STORAGE_PREFIX="claimcheck/"
```

#### 3.3 向量库（ChromaDB 持久化目录）

默认会写到仓库目录：`.chroma`（可改）：

```bash
export CHROMA_PERSIST_DIR="./.chroma"
export CHROMA_COLLECTION="morning_report"
```

#### 3.4 可选：LLM（SiliconFlow）

当前项目里有两类 LLM 调用：
- Parser 的论文总述（`tool_services/paper_analyse`）：**不配置 key 会返回空字符串**（仍可跑通链路）
- Overview 的领域综述（`tool_services/overview_service`）：**必须配置 SILICONFLOW2_API_KEY** 才能跑通 SUMMARY_REPORT
- Translator 的多模态翻译（`tool_services/translator_service`）：必须配置 `SILICONFLOW_API_KEY`（并建议配置 vision model）

常用变量：

```bash
# Parser summary（可选）
export SILICONFLOW_API_KEY="sk-buicstsfegdrvyvakdtqvwyhydmqwrpldpsyiaocnmftqmca"
export SILICONFLOW_API_BASE="https://api.siliconflow.cn/v1/chat/completions"
export SILICONFLOW_MODEL="deepseek-ai/DeepSeek-V3"

# Overview（必须，用于 SUMMARY_REPORT）
export SILICONFLOW2_API_KEY="sk-buicstsfegdrvyvakdtqvwyhydmqwrpldpsyiaocnmftqmca"
export SILICONFLOW2_API_BASE="https://api.siliconflow.cn/v1/chat/completions"
export SILICONFLOW2_MODEL="deepseek-ai/DeepSeek-V3"
```

---

### 4) 运行 Demo：启动服务并提交任务

#### 4.1 MORNING_REPORT（默认）

`run_demo.py` 会启动：Nexus + discovery + downloader + parser + indexer + overview（overview 仅在 SUMMARY_REPORT 时使用）。

```bash
python3 run_demo.py
```

输出：
- 会在终端打印最终 `data:morning_report:{trace_id}` 的 JSON
- 同时写入 MinIO（Claim Check）里对应 key

#### 4.2 SUMMARY_REPORT（领域综述）

该模式会先在 MinIO 写一个 `seed:summary_report:demo`，里面是若干 `pdf_url`，然后执行：
`parser(fan-out)` → `overview_service(聚合)` → 最终写入 `data:summary_report:{trace_id}`。

需要先设置 `SILICONFLOW2_API_KEY`：

```bash
DEMO_TASK_TYPE=SUMMARY_REPORT python3 run_demo.py
```

输出：
- 终端打印最终 `data:summary_report:{trace_id}`（包含 `overview_md`）
- 同时写入 MinIO

---

### 5) 常见问题

- **只拿到少于 limit 篇论文**：OpenAlex 返回的 work 未必都有可下载 `pdf_url`；系统会只调度可下载的候选。\n
- **部分论文解析失败**：PDF 可能无法提取文本（例如图片型 PDF）。当前编排允许部分失败，失败会记录在 `failures[]`，成功的仍会汇总。\n
- **MinIO / RabbitMQ 没启动**：会在服务启动或存储读写时报错。请先执行 `docker compose -f docker-compose.demo.yml up -d`。\n


# ResearchGO : 事件驱动微服务编排平台

ResearchGO 是一个基于 Python 的高性能、可扩展的微服务编排平台。它采用“编排中枢 (Nexus) + 多工具服务 (Tool Services)”的架构，通过 **事件驱动（Event-Driven）** 和 **凭证检查（Claim Check）** 模式，实现复杂长任务流（如学术早报、领域综述）的自动化调度与处理。

---

## 目录（Table of Contents）

- [1. 编排与调度策略](#1-编排与调度策略-the-orchestration-strategy)
- [2. 底层微服务业务逻辑](#2-底层微服务业务逻辑-microservices-deep-dive)
- [3. 项目目录结构](#3-项目目录结构)
- [4. 快速上手](#4-快速上手)
- [5. API 与文档入口](#5-api-与文档入口)
- [6. 常见问题（Troubleshooting）](#6-常见问题troubleshooting)

---

## 1. 编排与调度策略 (The Orchestration Strategy)

Nexus 是整个系统的“大脑”，其核心调度逻辑具有以下特点：

### 1.1 声明式工作流 (Declarative Workflows)
系统不再硬编码业务逻辑，而是通过 `nexus/config/workflows.yaml` 定义任务流。
- **Stage 类型**：
    - `single`: 一对一的服务调用。
    - `fan-out`: 一对多的任务分发（如发现 N 篇论文后，同时启动 N 个下载任务）。
    - `fan-in`: 多对一的任务聚合（如所有论文解析完成后，启动一个综述生成任务）。
- **状态机控制**：Nexus 内部维护每个 `trace_id` 的执行状态，只有当前阶段所有子任务成功（ACK）后，才会触发下一阶段。

### 1.2 凭证检查模式 (Claim Check Pattern)
为了解决微服务间传输大数据（如 PDF、高维向量）导致的带宽瓶颈：
- **传信不传物**：MQ 消息体仅包含 `trace_id` 与产物引用（如 `output_key` / `input_ref` / `result_ref`）。
- **数据面自治**：大对象通常由产物所属服务写入对象存储（如 MinIO）或服务自有存储；其他服务/编排层通过 **ref-only**（引用）与 **只读 Query API** 按需读取。
- **当前仓库实现要点（ref-only）**：Nexus 的 `/artifacts/*` 端点会根据 `artifacts_refs` 把 ref 映射到各微服务 Query API 并代理返回 JSON（而不是直接从 MinIO 透传字节流）。

### 1.3 容错与重试
- **软性失败容忍**：在扇出（Fan-out）阶段，允许部分子任务失败（如个别 PDF 无法下载），Nexus 会收集错误并继续推进后续流程，最终在报告中汇总 `failures`。
- **ACK 机制**：基于 RabbitMQ 的手动确认机制，确保服务崩溃时消息不丢失。

---

## 2. 底层微服务业务逻辑 (Microservices Deep Dive)

本平台由多个职责单一、水平扩展的工具服务组成：

### 2.1 Discovery Service (资源发现)
- **核心逻辑**：对接外部学术 API（如 OpenAlex）。
- **业务职责**：根据用户提供的 `query` 和 `limit` 进行语义搜索，过滤出带有有效 `pdf_url` 的元数据列表。
- **产出**：生成一份待下载清单（Manifest 或等价的结果对象），并提供只读查询接口供 Nexus fan-out 使用。

### 2.2 Download Service (高并发下载)
- **核心逻辑**：基于异步 I/O 的文件拉取引擎。
- **业务职责**：执行物理下载任务，支持多种反爬策略、Header 伪装及自动重试。
- **产出**：将 PDF 文件持久化至对象存储，并通过 file_ref / signed URL 等形式向外提供可读引用。

### 2.3 Parser Service (结构化解析)
- **核心逻辑**：PDF 解析器 + LLM 语义提取。
- **业务职责**：
    - **Tika/Docling 适配**：从 PDF 中提取原始文本和元数据。
    - **LLM 摘要**：调用 DeepSeek/GPT 模型，针对提取的文本生成核心摘要。
- **产出**：结构化的 Markdown 文档及摘要 JSON。

### 2.4 Indexing Service (向量索引)
- **核心逻辑**：文本嵌入（Embedding）与向量检索。
- **业务职责**：将解析后的文本切片，调用 Embedding 模型转化为高维向量，并存入 ChromaDB 集群。
- **产出**：建立可供后续检索的向量索引库。

### 2.5 Overview Service (领域综述)
- **核心逻辑**：多源数据融合（Data Fusion）。
- **业务职责**：这是典型的“扇入（Fan-in）”节点。它收集该任务下所有成功的 Parser 结果，利用大模型的长上下文能力（Long Context），生成一份跨论文的对比综述和趋势分析。
- **产出**：领域综述报告（Summary Report）。

### 2.6 Translator Service (多模态翻译)
- **核心逻辑**：Go 核心引擎 + Python 适配层。
- **业务职责**：
    - **学术优化**：内置 LaTeX 公式保护、代码块占位及引用格式保持。
    - **多模态支持**：支持纯文本、图片 OCR 翻译及 PDF 全文翻译。
    - **术语管控**：支持自定义术语库（Glossary），确保专业词汇翻译的一致性。
- **产出**：多语言版本的学术产出及翻译置信度评估。

---

## 3. 项目目录结构

```bash
.
├── nexus/                  # 编排中枢
│   ├── app/engine/         # 核心调度引擎 (Orchestrator/Workflows)
│   ├── app/api/            # 统一入口与报告 API
│   └── config/             # 工作流配置文件 (workflows.yaml)
├── tool_services/          # 工具服务集群 (各服务拥有独立运行环境)
│   ├── discovery_service/  # 搜索与过滤
│   ├── download_service/   # 异步下载中心
│   ├── parser_service/     # 格式转换与摘要
│   ├── indexing_service/   # 向量化与持久化
│   ├── overview_service/   # 高级聚合综述
│   └── translator_service/ # 多模态翻译 (Go/Python 混合)
├── nexus_sdk/              # 微服务接入标准 SDK
└── shared/                 # 协议契约 (Pydantic Models)
```

---

## 4. 快速上手

### 4.1 启动基础设施 (Docker)
```bash
docker compose -f docker-compose.demo.yml up -d
```

### 4.2 运行全链路 Demo
该脚本将模拟一个真实的“学术早报”任务提交：
```bash
python3 run_demo.py
```

### 4.3 核心 API 访问
- **任务状态查询**：`GET /api/v1/jobs/{trace_id}`
- **标准化报告获取**：`GET /api/v1/jobs/{trace_id}/report`（聚合了所有微服务的业务产出）

---

## 5. API 与文档入口

### 5.1 API Documentation（最终交付入口）

- [统一 API 参考（Nexus + Tool Services + Query APIs）](docs/API_REFERENCE.md)

### 5.2 补充文档（设计/架构/用法）

- [架构设计深度决策：Nexus 数据获取模式（Report + Artifacts）](docs/DATA_RETRIEVAL_ARCHITECTURE.md)
- [总体架构与编排策略（Orchestration + Microservices）](docs/ARCHITECTURE_OVERVIEW.md)
- [微服务集成规范](ARCHITECTURE_GUIDE.md)
- [统一报告 API 使用指南](docs/REPORT_API_USAGE.md)

---

## 6. 常见问题（Troubleshooting）

- **我应该用 report 还是 artifacts？**
  - 常规场景优先 `GET /api/v1/jobs/{trace_id}/report`；需要调试/验收再用 `GET /api/v1/jobs/{trace_id}/artifacts/{artifact_key}`（详见 `docs/API_REFERENCE.md` 的“阅读指南”）。
- **为什么拿 report 会 400？**
  - 任务未完成时 report 会返回 400；先轮询 `GET /api/v1/jobs/{trace_id}`，确认状态为 completed 再取报告。
- **artifacts 返回的 URL 能不能直接当 artifact_key？**
  - 不能。`artifacts` 字段是 `{artifact_key: download_url}`，应使用 key 或直接请求 value。

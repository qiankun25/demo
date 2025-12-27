# Nexus 编排服务 (Nexus Orchestration Service)

Nexus 编排服务负责管理文档处理工作流的生命周期。

## 功能特性

- **工作流编排**: 管理包含多个阶段（发现、下载、解析、索引）的复杂工作流。
- **事件驱动架构**: 使用 RabbitMQ 实现服务间的异步通信。
- **状态管理**: 使用 MinIO 持久化作业状态和上下文（采用 Claim-Check 模式）。
- **扇出/扇入 (Fan-out/Fan-in)**: 支持工作项的并行处理。
- **弹性设计**: 实现了重试逻辑、死信队列和优雅关闭。

## 项目结构

本项目采用基于 FastAPI 和事件驱动设计的模块化架构：

```
nexus/
├── app/
│   ├── api/            # API 路由与依赖注入
│   │   ├── routes.py       # REST 接口
│   │   └── dependencies.py # 依赖提供者
│   ├── core/           # 核心基础设施
│   │   ├── config.py       # 配置管理
│   │   ├── lifecycle.py    # 启动/关闭事件
│   │   ├── logging.py      # 结构化日志
│   │   └── retry.py        # 重试装饰器
│   ├── engine/         # 工作流引擎逻辑
│   │   ├── orchestrator.py # 工作流状态机
│   │   ├── workflows.py    # 工作流注册表
│   │   ├── handlers.py     # 事件处理器
│   │   └── utils.py        # 工作密钥工具
│   ├── infrastructure/ # 外部服务适配器
│   │   ├── mq_manager.py   # RabbitMQ 客户端
│   │   ├── storage.py      # MinIO/状态存储
│   │   └── metrics.py      # Prometheus 指标
│   ├── models/         # Pydantic 数据模型
│   │   ├── api_models.py   # 请求/响应模式
│   │   ├── messages.py     # 异步消息协议
│   │   └── state_models.py # 作业状态上下文
│   └── services/       # 业务逻辑服务
│       ├── job_service.py  # 作业提交
│       ├── report_service.py # 报告生成
│       └── status_service.py # 状态查询
├── config/             # 配置文件
│   └── workflows.yaml  # 工作流定义
├── tests/              # 测试套件
│   ├── unit/           # 单元测试
│   └── integration/    # 集成测试
├── Dockerfile          # 容器定义
├── docker-compose.yml  # 本地开发设置
└── requirements.txt    # Python 依赖
```

### 模块职责

- **app.api**: 处理 HTTP 请求，验证输入，并将依赖项注入到服务中。
- **app.core**: 提供横切关注点，如配置加载、日志设置和弹性模式。
- **app.engine**: 包含系统的“大脑”。`WorkflowOrchestrator` 协调执行流程，`handlers` 处理传入事件，`workflows` 管理定义。
- **app.infrastructure**: 抽象外部依赖。`MQManager` 处理健壮的 RabbitMQ 连接，而 `StorageBackend` 和 `StateManager` 管理 MinIO 中的持久化。
- **app.models**: 为 API 通信、内部状态和事件消息定义严格的数据模式，以确保类型安全。
- **app.services**: 封装高级业务逻辑，连接 API 层和核心引擎。

## API 端点

### 提交作业 (Submit Job)
`POST /api/v1/jobs`
```json
{
  "task_type": "MORNING_REPORT",
  "parameters": {
    "limit": 5,
    "query": "LLM Agents"
  }
}
```

### 获取作业状态 (Get Job Status)
`GET /api/v1/jobs/{trace_id}`

### 健康检查 (Health Check)
`GET /health`

## 配置

环境变量：
- `RABBITMQ_URL`: RabbitMQ 连接 URL。
- `MINIO_ENDPOINT`: MinIO 服务器地址。
- `MINIO_ACCESS_KEY`: MinIO 访问密钥。
- `MINIO_SECRET_KEY`: MinIO 密钥。
- `WORKFLOW_CONFIG_PATH`: 工作流定义 YAML 路径。

## 本地运行

```bash
docker-compose up --build
```

## 开发指南

安装依赖：
```bash
pip install -r requirements.txt
```

运行测试：
```bash
pytest tests/
```

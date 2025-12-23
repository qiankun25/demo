# 生产部署配置总结

本文档总结了为生产部署和 Dify 集成新增的所有配置文件和功能。

## 新增文件清单

### 1. 部署配置文件

| 文件                      | 说明                                                 |
| ------------------------- | ---------------------------------------------------- |
| `.env.production.example` | 生产环境配置模板，包含所有必需和可选的环境变量       |
| `docker-compose.prod.yml` | 生产环境 Docker Compose 配置，包含安全加固和资源限制 |
| `nginx.conf`              | Nginx 反向代理配置，支持 HTTPS 和负载均衡            |
| `init-db.sql`             | 数据库初始化脚本                                     |
| `Dockerfile`              | 优化的多阶段构建，支持开发和生产环境                 |

### 2. 部署脚本

| 文件                      | 说明                                                     |
| ------------------------- | -------------------------------------------------------- |
| `scripts/deploy.sh`       | 自动化部署脚本，包含环境检查、备份、构建、启动和健康检查 |
| `scripts/health-check.sh` | 健康检查脚本，验证所有服务组件                           |
| `scripts/validate-env.sh` | 环境变量验证脚本，检查配置完整性和安全性                 |

### 3. 文档

| 文件                    | 说明                       |
| ----------------------- | -------------------------- |
| `DEPLOYMENT.md`         | 完整的生产部署指南（中文） |
| `QUICKSTART.md`         | 5 分钟快速启动指南（中文） |
| `README.zh-CN.md`       | 中文版 README              |
| `DEPLOYMENT_SUMMARY.md` | 本文档                     |

### 4. 集成示例

| 文件                            | 说明                       |
| ------------------------------- | -------------------------- |
| `dify-integration-example.json` | Dify Workflow 完整集成示例 |

### 5. 应用代码增强

| 文件                     | 说明                                 |
| ------------------------ | ------------------------------------ |
| `app/config.py`          | 增强的配置管理，支持所有生产环境变量 |
| `app/middleware/auth.py` | API Key 认证中间件                   |
| `app/routes/health.py`   | 完整的健康检查端点                   |
| `app/main.py`            | 更新的应用入口，集成健康检查和认证   |

### 6. 工具文件

| 文件         | 说明                       |
| ------------ | -------------------------- |
| `Makefile`   | 常用命令快捷方式           |
| `.gitignore` | Git 忽略规则，保护敏感信息 |

## 主要功能

### 1. 环境变量配置

**支持的配置项**:

- 应用配置（端口、worker 数量等）
- 数据库配置（PostgreSQL）
- 缓存配置（Redis）
- 对象存储配置（MinIO/S3/阿里云 OSS）
- Celery 配置（并发数、队列等）
- 下载配置（超时、重试、文件大小限制）
- API 配置（速率限制、CORS、API Key）
- 日志配置（级别、格式）
- Webhook 配置（可选）
- 监控配置（Sentry、Prometheus）

**默认值**:
所有配置都有合理的默认值，只需修改关键的安全相关配置即可快速部署。

### 2. Docker 生产部署

**特性**:

- 多阶段构建，优化镜像大小
- 非 root 用户运行，提高安全性
- 健康检查配置
- 资源限制
- 日志轮转
- 服务依赖管理
- 自动重启策略

**服务组件**:

- FastAPI 应用（支持多 worker）
- Celery Worker（支持水平扩展）
- Celery Beat（定时任务调度）
- PostgreSQL（持久化存储）
- Redis（消息队列和缓存）
- MinIO（对象存储）
- Nginx（反向代理，可选）

### 3. 与 Dify 集成

**集成方式**:

1. HTTP Request 节点调用下载 API
2. 轮询或 Webhook 获取任务状态
3. 下载文件内容进行后续处理

**示例场景**:

- 文献下载与分析工作流
- 自动化文献收集
- 批量文献处理
- 文献内容提取和摘要

**配置要点**:

- 在 Dify 中配置 API Key 环境变量
- 使用 HTTP Request 节点
- 处理异步任务状态
- 错误处理和重试逻辑

### 4. 安全特性

**实现的安全措施**:

- API Key 认证
- HTTPS 支持（通过 Nginx）
- CORS 配置
- 密码强度验证
- 非 root 用户运行
- 环境变量保护
- 速率限制
- 安全头配置

### 5. 监控和日志

**监控功能**:

- 健康检查端点（/health, /health/live, /health/ready）
- 组件状态检查（数据库、Redis、存储）
- Prometheus 指标支持（可选）
- Sentry 错误追踪（可选）

**日志管理**:

- JSON 格式日志
- 日志级别配置
- 日志轮转
- 集中式日志收集支持

### 6. 运维工具

**部署工具**:

- 一键部署脚本
- 环境验证脚本
- 健康检查脚本
- Makefile 快捷命令

**备份和恢复**:

- 数据库备份脚本
- 数据库恢复脚本
- MinIO 数据备份指南

## 部署流程

### 开发环境

```bash
# 1. 启动服务
make dev

# 2. 查看日志
make logs

# 3. 运行测试
make test
```

### 生产环境

```bash
# 1. 初始化配置
make init-prod
nano .env.production  # 修改配置

# 2. 验证配置
./scripts/validate-env.sh

# 3. 部署
make deploy

# 4. 健康检查
make health
```

## 与其他服务集成

### 上游服务（触发下载）

任何服务都可以通过 HTTP API 触发下载：

```python
import requests

response = requests.post(
    "http://literature-service:8000/api/v1/download",
    headers={"X-API-Key": "your-key"},
    json={"url": "https://arxiv.org/pdf/xxx.pdf"}
)
```

### 下游服务（接收结果）

**方式 1: 轮询**

```python
while True:
    status = requests.get(f"http://literature-service:8000/api/v1/download/{task_id}")
    if status.json()["status"] == "completed":
        break
    time.sleep(2)
```

**方式 2: Webhook（配置 WEBHOOK_URL）**
服务会在任务完成时自动通知下游服务。

### Dify 集成

在 Dify Workflow 中：

1. 使用 HTTP Request 节点调用 API
2. 使用 Delay 节点等待处理
3. 使用 If-Else 节点判断状态
4. 使用 LLM 节点分析文件内容

详见 `dify-integration-example.json`

## 配置示例

### 最小配置（开发）

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/downloads
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### 推荐配置（生产）

```env
# 应用
APP_ENV=production
APP_WORKERS=4

# 数据库
DATABASE_URL=postgresql://prod_user:strong_password@db:5432/literature_downloads

# Redis
REDIS_URL=redis://:redis_password@redis:6379/0

# 对象存储
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_BUCKET=literature-papers
MINIO_SECURE=false

# 安全
ALLOWED_API_KEYS=key1,key2,key3
CORS_ORIGINS=https://your-dify-domain.com

# 日志
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### AWS S3 配置

```env
MINIO_ENDPOINT=s3.amazonaws.com
MINIO_ACCESS_KEY=your_aws_access_key
MINIO_SECRET_KEY=your_aws_secret_key
MINIO_BUCKET=your-bucket-name
MINIO_SECURE=true
AWS_REGION=us-east-1
```

## 扩展和优化

### 水平扩展

```bash
# 扩展 Celery worker
docker-compose -f docker-compose.prod.yml up -d --scale celery=3

# 扩展 API 服务
docker-compose -f docker-compose.prod.yml up -d --scale app=2
```

### 性能优化

1. **数据库优化**

   - 配置连接池
   - 添加索引
   - 定期清理旧数据

2. **缓存优化**

   - Redis 缓存频繁查询
   - 配置合适的过期时间

3. **存储优化**

   - 使用 CDN 加速下载
   - 配置对象生命周期

4. **Worker 优化**
   - 调整并发数
   - 配置任务优先级
   - 使用任务路由

## 监控指标

建议监控的指标：

- API 请求数和响应时间
- Celery 任务队列长度
- 下载成功率和失败率
- 存储使用量
- 数据库连接池状态
- Redis 内存使用
- 系统资源使用（CPU、内存、磁盘）

## 故障排查

常见问题和解决方案请参考：

- [DEPLOYMENT.md - 故障排查](./DEPLOYMENT.md#故障排查)
- [README.md - Troubleshooting](./README.md#troubleshooting)

## 下一步

1. **阅读文档**

   - [QUICKSTART.md](./QUICKSTART.md) - 快速开始
   - [DEPLOYMENT.md](./DEPLOYMENT.md) - 详细部署指南

2. **配置环境**

   - 复制 `.env.production.example`
   - 修改配置
   - 验证配置

3. **部署服务**

   - 运行部署脚本
   - 执行健康检查
   - 配置监控

4. **集成 Dify**

   - 配置 API Key
   - 创建 Workflow
   - 测试集成

5. **生产优化**
   - 配置 HTTPS
   - 设置备份
   - 配置监控告警

## 支持

如有问题，请：

1. 查看文档
2. 检查日志
3. 运行健康检查
4. 提交 Issue

---

**创建日期**: 2024-11-30
**版本**: 1.0.0

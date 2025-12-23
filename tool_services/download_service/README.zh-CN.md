# 文献下载服务

一个基于 FastAPI 和 Celery 构建的异步 PDF 下载服务，专为 Dify 平台的研究代理生态系统设计。该服务支持从多种来源（arXiv、Semantic Scholar、Springer 等）可靠下载学术文献，具有自动重试机制、MinIO 存储和基于 PostgreSQL 的任务跟踪功能。

## 特性

- **异步处理**: 使用 Celery 和 Redis 的非阻塞任务队列
- **自动重试**: 针对临时故障的指数退避重试逻辑（最多 3 次尝试）
- **对象存储**: PDF 文件存储在 MinIO（S3 兼容）
- **任务跟踪**: PostgreSQL 数据库记录任务状态和元数据
- **预签名 URL**: 安全的、有时限的文件访问（1 小时过期）
- **URL 验证**: 下载前的 URL 可达性检查
- **容器化**: 完整的 Docker Compose 部署

## 架构

```
客户端 → FastAPI → Redis 队列 → Celery Worker → MinIO 存储
                ↓                      ↓
            PostgreSQL ← ─ ─ ─ ─ ─ ─ ─ ┘
```

## 前置要求

- **Docker**: 20.10 或更高版本
- **Docker Compose**: 2.0 或更高版本

无需其他依赖 - 所有服务都在容器中运行。

## 快速开始

📖 **详细指南**: 查看 [QUICKSTART.md](./QUICKSTART.md) 获取 5 分钟快速启动指南

### 开发环境

```bash
# 启动所有服务
docker-compose up -d

# 或使用 Makefile
make dev

# 验证服务
curl http://localhost:8000/health

# 提交下载请求
curl -X POST http://localhost:8000/api/v1/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://arxiv.org/pdf/1706.03762.pdf", "source_type": "arxiv"}'

# 查询任务状态
curl http://localhost:8000/api/v1/download/{task_id}
```

### 生产环境

```bash
# 1. 准备配置
cp .env.production.example .env.production
nano .env.production  # 修改所有 CHANGE_ME 值

# 2. 验证配置
chmod +x scripts/validate-env.sh
./scripts/validate-env.sh

# 3. 部署
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# 或使用 Makefile
make init-prod  # 初始化配置
make deploy     # 部署
```

## API 端点

### POST /api/v1/download

提交新的下载任务。

**请求**:

```json
{
  "url": "https://arxiv.org/pdf/1706.03762.pdf",
  "source_type": "arxiv",
  "metadata": {
    "title": "Attention Is All You Need",
    "authors": "Vaswani et al."
  }
}
```

**响应**:

```json
{
  "task_id": "uuid",
  "status": "pending"
}
```

### GET /api/v1/download/{task_id}

查询下载任务状态。

**响应（成功）**:

```json
{
  "task_id": "uuid",
  "status": "completed",
  "file_url": "http://minio:9000/papers/...",
  "file_path": "uuid/filename.pdf",
  "metadata": {...}
}
```

### GET /health

健康检查端点。

**响应**:

```json
{
  "status": "healthy",
  "components": {
    "database": "ok",
    "redis": "ok",
    "storage": "ok"
  }
}
```

## 与 Dify 集成

### 配置 HTTP 请求节点

**创建下载任务**:

```yaml
Method: POST
URL: http://literature-download-service:8000/api/v1/download
Headers:
  Content-Type: application/json
  X-API-Key: { { env.LITERATURE_API_KEY } }
Body: { "url": "{{input.paper_url}}", "source_type": "{{input.source_type}}" }
```

**查询任务状态**:

```yaml
Method: GET
URL: http://literature-download-service:8000/api/v1/download/{{task_id}}
Headers:
  X-API-Key: { { env.LITERATURE_API_KEY } }
```

完整的 Dify 工作流示例请参考 [dify-integration-example.json](./dify-integration-example.json)

### 在 Dify 中配置

1. 进入 Dify 设置 → 环境变量
2. 添加变量：
   - 名称: `LITERATURE_API_KEY`
   - 值: 你的 API Key
3. 在 Workflow 中使用: `{{env.LITERATURE_API_KEY}}`

## 环境变量配置

### 必需变量

| 变量名             | 说明                  | 示例                                       |
| ------------------ | --------------------- | ------------------------------------------ |
| `DATABASE_URL`     | PostgreSQL 连接字符串 | `postgresql://user:pass@db:5432/downloads` |
| `REDIS_URL`        | Redis 连接字符串      | `redis://:password@redis:6379/0`           |
| `MINIO_ENDPOINT`   | MinIO 端点            | `minio:9000`                               |
| `MINIO_ACCESS_KEY` | MinIO 访问密钥        | `your-access-key`                          |
| `MINIO_SECRET_KEY` | MinIO 密钥            | `your-secret-key`                          |

### 可选变量

| 变量名             | 说明                 | 默认值              |
| ------------------ | -------------------- | ------------------- |
| `MINIO_BUCKET`     | 存储桶名称           | `papers`            |
| `MINIO_SECURE`     | 使用 HTTPS           | `false`             |
| `MAX_FILE_SIZE`    | 最大文件大小（字节） | `104857600` (100MB) |
| `DOWNLOAD_TIMEOUT` | 下载超时（秒）       | `300`               |
| `API_RATE_LIMIT`   | API 速率限制         | `100`               |
| `ALLOWED_API_KEYS` | API 密钥列表         | ``                  |

完整配置说明请参考 [DEPLOYMENT.md](./DEPLOYMENT.md)

## 常用命令

使用 Makefile 简化操作：

```bash
# 开发
make dev          # 启动开发环境
make logs         # 查看日志
make test         # 运行测试
make restart      # 重启服务

# 生产
make prod         # 启动生产环境
make deploy       # 运行部署脚本
make health       # 健康检查

# 其他
make shell        # 进入应用容器
make db-shell     # 进入数据库
make backup-db    # 备份数据库
make clean        # 清理所有数据
```

## 测试

```bash
# 运行所有测试
make test

# 运行测试并生成覆盖率报告
make test-cov

# 或使用 pytest
docker-compose run --rm app pytest
docker-compose run --rm app pytest --cov=app
```

## 监控和日志

### 查看日志

```bash
# 所有服务
docker-compose logs -f

# 特定服务
docker-compose logs -f app
docker-compose logs -f celery

# 使用 Makefile
make logs
make logs-app
make logs-celery
```

### 访问服务

- **API 文档**: http://localhost:8000/docs
- **MinIO 控制台**: http://localhost:9001 (minioadmin/minioadmin)
- **健康检查**: http://localhost:8000/health

## 故障排查

### 任务一直处于 pending 状态

**原因**: Celery worker 未运行

**解决**:

```bash
docker-compose ps celery
docker-compose restart celery
```

### 下载失败

**原因**: URL 无法访问或网络问题

**解决**:

```bash
# 测试 URL
curl -I <pdf-url>

# 查看错误日志
docker-compose logs celery | grep ERROR
```

### 存储连接错误

**原因**: MinIO 未就绪或配置错误

**解决**:

```bash
# 检查 MinIO
curl http://localhost:9000/minio/health/live

# 访问控制台
open http://localhost:9001
```

更多故障排查信息请参考 [DEPLOYMENT.md](./DEPLOYMENT.md#故障排查)

## 生产部署

📖 **完整部署指南**: [DEPLOYMENT.md](./DEPLOYMENT.md)

### 安全建议

1. 修改所有默认密码和密钥
2. 配置 `ALLOWED_API_KEYS` 保护 API
3. 启用 HTTPS (`MINIO_SECURE=true`)
4. 限制 `CORS_ORIGINS` 到特定域名
5. 使用反向代理（Nginx）
6. 配置防火墙规则
7. 定期备份数据

### 扩展

```bash
# 水平扩展 Celery worker
docker-compose up -d --scale celery=3

# 使用 Makefile
make scale-workers
```

### 备份和恢复

```bash
# 备份数据库
make backup-db

# 恢复数据库
make restore-db FILE=backups/backup_20231201.sql
```

## 项目结构

```
.
├── app/                      # 应用代码
│   ├── models/              # 数据模型
│   ├── routes/              # API 路由
│   ├── services/            # 业务逻辑
│   ├── tasks/               # Celery 任务
│   ├── middleware/          # 中间件
│   ├── config.py            # 配置
│   ├── database.py          # 数据库
│   └── main.py              # 应用入口
├── tests/                   # 测试
├── scripts/                 # 部署脚本
├── docker-compose.yml       # 开发环境
├── docker-compose.prod.yml  # 生产环境
├── Dockerfile               # 容器镜像
├── requirements.txt         # Python 依赖
├── .env.production.example  # 配置模板
├── DEPLOYMENT.md            # 部署文档
├── QUICKSTART.md            # 快速开始
└── dify-integration-example.json  # Dify 集成示例
```

## 文档

- [快速开始指南](./docs/QUICKSTART.md) - 5 分钟快速启动
- [部署文档](./docs/DEPLOYMENT.md) - 完整的生产部署指南
- [API 文档](http://localhost:8000/docs) - 交互式 API 文档
- [Dify 集成示例](./docs/dify-integration-example.json) - 工作流配置

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 支持

如有问题，请：

1. 查看 [故障排查指南](./DEPLOYMENT.md#故障排查)
2. 检查 [GitHub Issues](https://github.com/your-repo/issues)
3. 联系技术支持

---

**English Version**: [README.md](./README.md)

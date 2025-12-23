# 生产部署指南

本文档介绍如何在生产环境中部署文献下载服务，以及如何与 Dify 等上下游服务集成。

## 目录

- [环境要求](#环境要求)
- [环境变量配置](#环境变量配置)
- [Docker 部署](#docker-部署)
- [与 Dify 集成](#与-dify-集成)
- [监控和日志](#监控和日志)
- [故障排查](#故障排查)

## 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB 可用内存
- 至少 10GB 可用磁盘空间

## 环境变量配置

### 生产环境配置文件

创建 `.env.production` 文件用于生产环境：

```bash
# 应用配置
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000
APP_WORKERS=4

# 数据库配置（PostgreSQL）
DATABASE_URL=postgresql://prod_user:Dd123@db:5432/literature_downloads

# Redis 配置
REDIS_URL=redis://:Dd123@redis:6379/0

# Celery 配置
CELERY_BROKER_URL=redis://:Dd123@redis:6379/0
CELERY_RESULT_BACKEND=redis://:Dd123@redis:6379/1
CELERY_WORKER_CONCURRENCY=4

# MinIO/S3 对象存储配置
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=CHANGE_ME_ACCESS_KEY
MINIO_SECRET_KEY=CHANGE_ME_SECRET_KEY
MINIO_BUCKET=literature-papers
MINIO_SECURE=false

# 如果使用 AWS S3，配置如下：
# MINIO_ENDPOINT=s3.amazonaws.com
# MINIO_ACCESS_KEY=your_aws_access_key
# MINIO_SECRET_KEY=your_aws_secret_key
# MINIO_BUCKET=your-bucket-name
# MINIO_SECURE=true
# AWS_REGION=us-east-1

# 下载配置
MAX_FILE_SIZE=104857600  # 100MB
DOWNLOAD_TIMEOUT=300     # 5分钟
MAX_RETRIES=3

# API 配置
API_RATE_LIMIT=100       # 每分钟请求数
CORS_ORIGINS=https://your-dify-domain.com,https://your-frontend-domain.com

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=json

# 安全配置
API_KEY_HEADER=X-API-Key
ALLOWED_API_KEYS=key1,key2,key3  # 用逗号分隔多个 API Key
```

### 配置说明

| 变量名                      | 必填 | 默认值      | 说明                  |
| --------------------------- | ---- | ----------- | --------------------- |
| `DATABASE_URL`              | 是   | -           | PostgreSQL 连接字符串 |
| `REDIS_URL`                 | 是   | -           | Redis 连接字符串      |
| `MINIO_ENDPOINT`            | 是   | -           | MinIO/S3 端点地址     |
| `MINIO_ACCESS_KEY`          | 是   | -           | 对象存储访问密钥      |
| `MINIO_SECRET_KEY`          | 是   | -           | 对象存储密钥          |
| `MINIO_BUCKET`              | 否   | `papers`    | 存储桶名称            |
| `MINIO_SECURE`              | 否   | `false`     | 是否使用 HTTPS        |
| `APP_WORKERS`               | 否   | `4`         | Uvicorn worker 数量   |
| `CELERY_WORKER_CONCURRENCY` | 否   | `4`         | Celery worker 并发数  |
| `MAX_FILE_SIZE`             | 否   | `104857600` | 最大文件大小（字节）  |
| `DOWNLOAD_TIMEOUT`          | 否   | `300`       | 下载超时时间（秒）    |
| `API_RATE_LIMIT`            | 否   | `100`       | API 速率限制          |
| `CORS_ORIGINS`              | 否   | `*`         | 允许的 CORS 源        |

## Docker 部署

### 1. 准备生产环境配置

```bash
# 复制环境配置模板
cp .env.production.example .env.production

# 编辑配置文件，修改所有 CHANGE_ME 开头的值
nano .env.production
```

### 2. 使用 Docker Compose 部署

```bash
# 拉取最新镜像
docker-compose -f docker-compose.prod.yml pull

# 启动所有服务
docker-compose -f docker-compose.prod.yml up -d

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f app
```

### 3. 初始化数据库和存储

```bash
# 运行数据库迁移
docker-compose -f docker-compose.prod.yml exec app alembic upgrade head

# 创建 MinIO 存储桶
docker-compose -f docker-compose.prod.yml exec app python -c "
from app.services.storage import storage_service
storage_service.ensure_bucket()
print('Storage bucket created successfully')
"
```

### 4. 健康检查

```bash
# 检查 API 健康状态
curl http://localhost:8000/health

# 检查 Celery worker 状态
docker-compose -f docker-compose.prod.yml exec celery celery -A app.celery_app inspect active
```

## 与 Dify 集成

### 架构说明

```
┌─────────┐      ┌──────────────────┐      ┌─────────────┐
│  Dify   │─────>│ Literature       │─────>│  External   │
│ Workflow│      │ Download Service │      │  Sources    │
└─────────┘      └──────────────────┘      └─────────────┘
     │                    │                        │
     │                    ▼                        │
     │           ┌─────────────────┐              │
     └──────────>│  MinIO/S3       │<─────────────┘
                 │  Object Storage │
                 └─────────────────┘
```

### 在 Dify 中配置 HTTP 请求节点

#### 1. 创建下载任务

**节点类型**: HTTP Request

**配置**:

```yaml
Method: POST
URL: http://literature-download-service:8000/api/v1/download
Headers:
  Content-Type: application/json
  X-API-Key: ${API_KEY}
Body:
  {
    "url": "{{input.paper_url}}",
    "source_type": "{{input.source_type}}",
    "metadata":
      {
        "title": "{{input.title}}",
        "authors": "{{input.authors}}",
        "year": "{{input.year}}",
      },
  }
```

**输出变量**:

- `task_id`: 下载任务 ID
- `status`: 任务状态

#### 2. 查询任务状态

**节点类型**: HTTP Request

**配置**:

```yaml
Method: GET
URL: http://literature-download-service:8000/api/v1/download/{{task_id}}
Headers:
  X-API-Key: ${API_KEY}
```

**输出变量**:

- `status`: 任务状态 (pending/processing/completed/failed)
- `file_url`: 文件下载链接（完成时）
- `error`: 错误信息（失败时）

#### 3. 获取文件内容

**节点类型**: HTTP Request

**配置**:

```yaml
Method: GET
URL: { { file_url } }
```

### Dify Workflow 示例

```yaml
workflow:
  name: "文献下载与分析"

  nodes:
    - id: input
      type: start
      outputs:
        - paper_url
        - source_type

    - id: download
      type: http-request
      config:
        method: POST
        url: http://literature-download-service:8000/api/v1/download
        headers:
          X-API-Key: ${API_KEY}
        body:
          url: "{{input.paper_url}}"
          source_type: "{{input.source_type}}"
      outputs:
        - task_id

    - id: wait
      type: delay
      config:
        seconds: 5

    - id: check_status
      type: http-request
      config:
        method: GET
        url: http://literature-download-service:8000/api/v1/download/{{download.task_id}}
        headers:
          X-API-Key: ${API_KEY}
      outputs:
        - status
        - file_url

    - id: condition
      type: if-else
      config:
        condition: "{{check_status.status}} == 'completed'"
        if_true: process_file
        if_false: retry_or_fail

    - id: process_file
      type: http-request
      config:
        method: GET
        url: "{{check_status.file_url}}"
      outputs:
        - file_content

    - id: analyze
      type: llm
      config:
        prompt: "分析以下文献内容：{{process_file.file_content}}"
```

### API Key 管理

在 Dify 中配置环境变量：

1. 进入 Dify 设置 → 环境变量
2. 添加变量：
   - 名称: `LITERATURE_API_KEY`
   - 值: 从文献下载服务获取的 API Key
3. 在 Workflow 中引用: `${LITERATURE_API_KEY}`

## 与其他服务集成

### 上游服务（触发下载）

任何服务都可以通过 HTTP API 触发下载：

```python
import requests

# 创建下载任务
response = requests.post(
    "http://literature-download-service:8000/api/v1/download",
    headers={"X-API-Key": "your-api-key"},
    json={
        "url": "https://arxiv.org/pdf/2301.00001.pdf",
        "source_type": "arxiv",
        "metadata": {"title": "Paper Title"}
    }
)
task_id = response.json()["task_id"]

# 轮询任务状态
import time
while True:
    status_response = requests.get(
        f"http://literature-download-service:8000/api/v1/download/{task_id}",
        headers={"X-API-Key": "your-api-key"}
    )
    data = status_response.json()

    if data["status"] == "completed":
        file_url = data["file_url"]
        print(f"Download completed: {file_url}")
        break
    elif data["status"] == "failed":
        print(f"Download failed: {data['error']}")
        break

    time.sleep(2)
```

### 下游服务（接收文件）

下载完成后，可以通过 Webhook 通知下游服务：

```python
# 在配置中添加 Webhook URL
WEBHOOK_URL=https://your-service.com/webhook/download-completed

# 服务会在下载完成时发送 POST 请求：
{
  "task_id": "uuid",
  "status": "completed",
  "file_url": "http://minio:9000/papers/file.pdf",
  "metadata": {...}
}
```

## 反向代理配置（Nginx）

```nginx
upstream literature_service {
    server localhost:8000;
}

server {
    listen 80;
    server_name literature-api.yourdomain.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name literature-api.yourdomain.com;

    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 上传大小限制
    client_max_body_size 100M;

    location / {
        proxy_pass http://literature_service;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # 健康检查端点
    location /health {
        proxy_pass http://literature_service/health;
        access_log off;
    }
}
```

## 监控和日志

### 日志收集

```bash
# 查看应用日志
docker-compose -f docker-compose.prod.yml logs -f app

# 查看 Celery worker 日志
docker-compose -f docker-compose.prod.yml logs -f celery

# 导出日志到文件
docker-compose -f docker-compose.prod.yml logs --no-color > logs/app.log
```

### 监控指标

推荐使用 Prometheus + Grafana 监控：

- API 请求数和响应时间
- Celery 任务队列长度
- 下载成功率和失败率
- 存储使用量
- 数据库连接池状态

### 健康检查端点

- `GET /health` - 服务健康状态
- `GET /metrics` - Prometheus 指标（需要配置）

## 故障排查

### 常见问题

#### 1. 下载任务一直处于 pending 状态

**原因**: Celery worker 未启动或无法连接到 Redis

**解决**:

```bash
# 检查 Celery worker 状态
docker-compose -f docker-compose.prod.yml ps celery

# 查看 Celery 日志
docker-compose -f docker-compose.prod.yml logs celery

# 重启 Celery worker
docker-compose -f docker-compose.prod.yml restart celery
```

#### 2. 文件上传到 MinIO 失败

**原因**: MinIO 连接配置错误或存储桶不存在

**解决**:

```bash
# 检查 MinIO 连接
docker-compose -f docker-compose.prod.yml exec app python -c "
from app.services.storage import storage_service
print(storage_service.client.bucket_exists(storage_service.bucket_name))
"

# 手动创建存储桶
docker-compose -f docker-compose.prod.yml exec app python -c "
from app.services.storage import storage_service
storage_service.ensure_bucket()
"
```

#### 3. 数据库连接失败

**原因**: PostgreSQL 未就绪或连接字符串错误

**解决**:

```bash
# 检查数据库连接
docker-compose -f docker-compose.prod.yml exec db pg_isready -U prod_user

# 测试连接
docker-compose -f docker-compose.prod.yml exec app python -c "
from app.database import engine
with engine.connect() as conn:
    print('Database connection successful')
"
```

### 日志级别调整

临时调整日志级别以获取更多调试信息：

```bash
# 设置环境变量
docker-compose -f docker-compose.prod.yml exec app \
  env LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

## 备份和恢复

### 数据库备份

```bash
# 备份数据库
docker-compose -f docker-compose.prod.yml exec db \
  pg_dump -U prod_user literature_downloads > backup_$(date +%Y%m%d).sql

# 恢复数据库
docker-compose -f docker-compose.prod.yml exec -T db \
  psql -U prod_user literature_downloads < backup_20231201.sql
```

### MinIO 数据备份

```bash
# 使用 mc (MinIO Client) 备份
mc mirror minio/literature-papers /backup/minio/
```

## 扩展和优化

### 水平扩展

```bash
# 增加 Celery worker 数量
docker-compose -f docker-compose.prod.yml up -d --scale celery=3

# 增加 API 服务实例
docker-compose -f docker-compose.prod.yml up -d --scale app=2
```

### 性能优化建议

1. 使用 Redis 缓存频繁访问的数据
2. 配置 CDN 加速文件下载
3. 启用数据库连接池
4. 使用异步 I/O 处理文件操作
5. 配置适当的 worker 并发数

## 安全建议

1. 使用强密码和 API Key
2. 启用 HTTPS/TLS
3. 配置防火墙规则
4. 定期更新依赖包
5. 限制 API 访问速率
6. 启用审计日志
7. 使用密钥管理服务（如 AWS Secrets Manager）

## 支持

如有问题，请查看：

- GitHub Issues
- 文档: https://docs.yourdomain.com
- 邮件: support@yourdomain.com

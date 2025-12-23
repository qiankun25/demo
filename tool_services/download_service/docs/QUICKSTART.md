# 快速开始指南

本指南帮助你在 5 分钟内启动文献下载服务。

## 开发环境快速启动

### 1. 启动所有服务

```bash
docker-compose up -d
```

等待所有服务启动（约 30 秒）。

### 2. 验证服务

```bash
curl http://localhost:8000/health
```

应该返回：

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

### 3. 测试下载

**提交下载任务**：

```bash
curl -X POST http://localhost:8000/api/v1/download \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://arxiv.org/pdf/1706.03762.pdf",
    "source_type": "arxiv"
  }'
```

返回：

```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending"
}
```

**查询任务状态**：

```bash
curl http://localhost:8000/api/v1/download/123e4567-e89b-12d3-a456-426614174000
```

等待几秒后，状态变为 `completed`，你会得到文件下载链接。

### 4. 访问服务

- **API 文档**: http://localhost:8000/docs
- **MinIO 控制台**: http://localhost:9001 (minioadmin/minioadmin)

## 生产环境快速部署

### 1. 准备配置

```bash
# 复制配置模板
cp .env.production.example .env.production

# 编辑配置（必须修改所有 CHANGE_ME 值）
nano .env.production
```

**必须修改的配置**：

- `POSTGRES_PASSWORD`: 数据库密码
- `REDIS_PASSWORD`: Redis 密码
- `MINIO_ACCESS_KEY`: MinIO 访问密钥
- `MINIO_SECRET_KEY`: MinIO 密钥
- `ALLOWED_API_KEYS`: API 访问密钥

### 2. 运行部署脚本

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

脚本会自动：

- 检查环境
- 备份数据（如果有）
- 构建镜像
- 启动服务
- 运行数据库迁移
- 初始化存储
- 执行健康检查

### 3. 验证部署

```bash
chmod +x scripts/health-check.sh
./scripts/health-check.sh
```

## 与 Dify 集成

### 在 Dify 中配置环境变量

1. 进入 Dify 设置 → 环境变量
2. 添加变量：
   - 名称: `LITERATURE_API_KEY`
   - 值: 你的 API Key（在 `.env.production` 中配置的）

### 创建 HTTP 请求节点

**下载文献**：

```yaml
Method: POST
URL: http://literature-download-service:8000/api/v1/download
Headers:
  Content-Type: application/json
  X-API-Key: { { env.LITERATURE_API_KEY } }
Body: { "url": "{{input.paper_url}}", "source_type": "arxiv" }
```

**查询状态**：

```yaml
Method: GET
URL: http://literature-download-service:8000/api/v1/download/{{task_id}}
Headers:
  X-API-Key: { { env.LITERATURE_API_KEY } }
```

完整示例请参考 [dify-integration-example.json](./dify-integration-example.json)

## 常用命令

### 查看日志

```bash
# 应用日志
docker-compose logs -f app

# Celery worker 日志
docker-compose logs -f celery

# 所有服务日志
docker-compose logs -f
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart app
docker-compose restart celery
```

### 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷（清空所有数据）
docker-compose down -v
```

### 扩展 Worker

```bash
# 运行 3 个 Celery worker
docker-compose up -d --scale celery=3
```

## 故障排查

### 任务一直 pending

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

# 查看详细错误
docker-compose logs celery | grep ERROR
```

### 存储错误

**原因**: MinIO 未就绪或配置错误

**解决**:

```bash
# 检查 MinIO
curl http://localhost:9000/minio/health/live

# 访问控制台
open http://localhost:9001
```

## 下一步

- 阅读完整的 [部署文档](./DEPLOYMENT.md)
- 查看 [API 文档](http://localhost:8000/docs)
- 了解 [Dify 集成示例](./dify-integration-example.json)

## 获取帮助

如有问题，请：

1. 查看日志：`docker-compose logs`
2. 检查健康状态：`curl http://localhost:8000/health`
3. 参考 [故障排查指南](./DEPLOYMENT.md#故障排查)

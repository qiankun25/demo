# Dify 插件集成指南

## OpenAPI Schema 修正说明

已修正 `docs/openapi.json` 文件，使其与实际 API 路由完全匹配。

### 主要修正内容

1. **路由路径修正**

   - ❌ 错误：`/api/v1/download` 和 `/api/v1/download/{task_id}`
   - ✅ 正确：`/download` 和 `/download/{task_id}`
   - 原因：项目中没有使用 `/api/v1` 前缀

2. **移除安全认证要求**

   - 移除了 `security` 字段中的 `ApiKeyAuth` 要求
   - 移除了 `securitySchemes` 定义
   - 原因：当前路由实现中未强制要求 API Key 认证（开发模式下可选）

3. **保留完整的响应示例**
   - 保留了 `pending`、`success`、`failed` 三种状态的完整示例
   - 包含时间戳字段 `created_at` 和 `updated_at`

## 在 Dify 中使用

### 1. 导入 OpenAPI 插件

1. 登录 Dify 工作台
2. 进入「工具」→「自定义工具」
3. 选择「导入 OpenAPI Schema」
4. 上传 `docs/openapi.json` 文件

### 2. 配置服务器地址

**⚠️ 重要**：在 Dify 中导入 OpenAPI 后，必须选择正确的服务器地址，否则会出现 "Reached maximum retries" 错误。

#### ✅ 推荐配置（你的当前环境）

**Dify 在 Docker 容器中，本服务在宿主机运行**

```
http://host.docker.internal:8000
```

这是 Docker Desktop 提供的特殊 DNS 名称，允许容器访问宿主机上的服务。

**验证方法**：

```bash
# 从 Dify 容器内测试连接
docker exec docker-api-1 curl http://host.docker.internal:8000/health
```

如果返回 `{"status":"healthy",...}`，说明地址正确。

#### 其他场景

**场景 A：Dify 和本服务在同一 Docker 网络**

```
http://download_service-app-1:8000
```

**场景 B：本地测试（Dify 不在容器中）**

```
http://localhost:8000
```

**场景 C：远程服务器部署**

```
http://YOUR_SERVER_IP:8000
或
https://your-domain.com
```

### 3. 测试 API 调用

#### 创建下载任务

```json
POST /download
{
  "url": "https://arxiv.org/pdf/2301.00001.pdf"
}
```

响应：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

#### 查询任务状态

```
GET /download/{task_id}
```

响应（成功时）：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "success",
  "file_url": "http://minio:9000/papers/file.pdf?X-Amz-Expires=3600",
  "error_message": null,
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:05:00Z"
}
```

### 4. 在 Dify 工作流中使用

1. 创建新的工作流
2. 添加「HTTP 请求」节点或使用导入的自定义工具
3. 配置两个步骤：
   - 步骤 1：调用 `createDownloadTask` 创建任务
   - 步骤 2：等待几秒后调用 `getTaskStatus` 查询结果
4. 使用返回的 `file_url` 进行后续处理

### 5. 注意事项

- `file_url` 是预签名 URL，有效期为 1 小时
- 任务状态包括：`pending`（等待）、`processing`（处理中）、`success`（成功）、`failed`（失败）
- 建议在工作流中添加重试逻辑，因为下载可能需要一些时间
- 如果启用了 API Key 认证，需要在请求头中添加 `X-API-Key`

## 故障排查

### ❌ 错误：Reached maximum retries for URL http://localhost:8000/download

**原因**：Dify 在 Docker 容器中运行，无法通过 `localhost` 访问宿主机服务。

**解决方案**：

1. 重新导入 `docs/openapi.json`（已更新默认服务器为 `host.docker.internal:8000`）
2. 或在 Dify 工具配置中手动修改服务器地址为 `http://host.docker.internal:8000`

**验证**：

```bash
# 测试从 Dify 容器访问服务
docker exec docker-api-1 curl http://host.docker.internal:8000/health
```

### 连接失败（其他原因）

- 检查服务是否正常运行：`curl http://localhost:8000/health`
- 检查 Docker 网络配置
- 确认防火墙规则
- 查看服务日志：`docker-compose logs app`

### 任务一直处于 pending 状态

- 检查 Celery worker 是否运行：`docker-compose ps`
- 查看 worker 日志：`docker-compose logs worker`
- 检查 Redis 连接

### 文件 URL 无法访问

- 检查 MinIO 服务状态
- 确认 `MINIO_EXTERNAL_ENDPOINT` 配置正确
- 验证预签名 URL 是否过期

## 相关文档

- [快速开始](./QUICKSTART.md)
- [部署指南](./DEPLOYMENT.md)
- [架构说明](./ARCHITECTURE.md)

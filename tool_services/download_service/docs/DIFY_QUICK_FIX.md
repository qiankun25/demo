# Dify 连接问题快速修复

## 问题

在 Dify 中测试工具时出现错误：

```
Reached maximum retries (0) for URL http://localhost:8000/download
```

## 原因

Dify 运行在 Docker 容器中，无法通过 `localhost` 访问宿主机上的服务。

## 解决方案

### 方法 1：重新导入 OpenAPI（推荐）

1. 删除现有的自定义工具
2. 重新导入 `docs/openapi.json`（已更新默认服务器地址）
3. 系统会自动选择 `http://host.docker.internal:8000`

### 方法 2：手动修改服务器地址

如果不想重新导入，可以在 Dify 工具配置中：

1. 找到服务器地址配置
2. 将 `http://localhost:8000` 改为 `http://host.docker.internal:8000`
3. 保存并重新测试

## 验证

运行以下命令验证连接：

```powershell
# 测试从 Dify 容器访问服务
docker exec docker-api-1 curl http://host.docker.internal:8000/health
```

应该返回：

```json
{
  "status": "healthy",
  "components": { "database": "ok", "redis": "ok", "storage": "ok" }
}
```

## 测试工具调用

在 Dify 中测试 `createDownloadTask` 工具：

**输入参数**：

```json
{
  "url": "https://arxiv.org/pdf/2301.00001.pdf"
}
```

**预期响应**：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

然后使用返回的 `task_id` 调用 `getTaskStatus` 查询下载结果。

## 其他服务器地址选项

根据你的部署环境，可以选择：

| 场景                                 | 服务器地址                                         |
| ------------------------------------ | -------------------------------------------------- |
| Dify 在 Docker，服务在宿主机（当前） | `http://host.docker.internal:8000`                 |
| Dify 和服务在同一 Docker 网络        | `http://download_service-app-1:8000`               |
| Dify 不在容器中                      | `http://localhost:8000`                            |
| 远程服务器                           | `http://YOUR_IP:8000` 或 `https://your-domain.com` |

## 完整文档

详细的集成指南请查看：[DIFY_INTEGRATION.md](./DIFY_INTEGRATION.md)

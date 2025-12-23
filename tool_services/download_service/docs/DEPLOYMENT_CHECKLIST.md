# 生产部署检查清单

在部署到生产环境之前，请确保完成以下所有检查项。

## 部署前检查

### 1. 环境配置 ✓

- [ ] 已复制 `.env.production.example` 为 `.env.production`
- [ ] 已修改所有 `CHANGE_ME` 值
- [ ] 数据库密码强度足够（至少 12 个字符）
- [ ] Redis 密码已配置
- [ ] MinIO 访问密钥和密钥已配置
- [ ] API Keys 已配置（`ALLOWED_API_KEYS`）
- [ ] CORS 源已限制到特定域名
- [ ] 运行了 `./scripts/validate-env.sh` 验证配置

### 2. 安全配置 ✓

- [ ] 所有默认密码已修改
- [ ] API Key 认证已启用
- [ ] CORS 已正确配置
- [ ] 准备好 SSL 证书（如使用 Nginx）
- [ ] 防火墙规则已配置
- [ ] 数据库端口未公开暴露
- [ ] Redis 端口未公开暴露

### 3. 基础设施 ✓

- [ ] Docker 已安装（20.10+）
- [ ] Docker Compose 已安装（2.0+）
- [ ] 服务器有足够的资源（至少 2GB 内存，10GB 磁盘）
- [ ] 网络连接正常
- [ ] DNS 已配置（如需要）

### 4. 备份策略 ✓

- [ ] 数据库备份计划已制定
- [ ] MinIO 数据备份计划已制定
- [ ] 备份存储位置已确定
- [ ] 恢复流程已测试

## 部署步骤

### 1. 准备阶段

```bash
# 克隆或上传代码
cd /path/to/literature-download-service

# 初始化生产配置
make init-prod

# 编辑配置
nano .env.production

# 验证配置
chmod +x scripts/validate-env.sh
./scripts/validate-env.sh
```

- [ ] 代码已部署到服务器
- [ ] 配置文件已创建并验证
- [ ] 脚本已添加执行权限

### 2. 部署阶段

```bash
# 运行部署脚本
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# 或手动部署
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

- [ ] 镜像构建成功
- [ ] 所有服务已启动
- [ ] 数据库迁移已执行
- [ ] 存储桶已创建

### 3. 验证阶段

```bash
# 健康检查
chmod +x scripts/health-check.sh
./scripts/health-check.sh

# 或手动检查
curl http://localhost:8000/health
docker-compose -f docker-compose.prod.yml ps
```

- [ ] 健康检查通过
- [ ] 所有服务状态正常
- [ ] API 可访问
- [ ] Celery worker 运行正常

### 4. 功能测试

```bash
# 测试下载功能
curl -X POST http://localhost:8000/api/v1/download \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"url": "https://arxiv.org/pdf/1706.03762.pdf", "source_type": "arxiv"}'

# 查询任务状态
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/download/{task_id}
```

- [ ] 可以创建下载任务
- [ ] 任务状态可查询
- [ ] 文件下载成功
- [ ] 文件可通过 URL 访问

## 部署后配置

### 1. Nginx 配置（如使用）

```bash
# 启动 Nginx
docker-compose -f docker-compose.prod.yml --profile with-nginx up -d

# 配置 SSL 证书
# 将证书放到 ssl/ 目录
```

- [ ] Nginx 已启动
- [ ] SSL 证书已配置
- [ ] HTTPS 访问正常
- [ ] HTTP 自动重定向到 HTTPS

### 2. 监控配置

- [ ] 日志收集已配置
- [ ] 监控告警已设置
- [ ] Sentry 已配置（如使用）
- [ ] Prometheus 已配置（如使用）

### 3. 备份配置

```bash
# 测试数据库备份
make backup-db

# 配置定时备份（crontab）
0 2 * * * cd /path/to/service && make backup-db
```

- [ ] 数据库备份测试成功
- [ ] 定时备份已配置
- [ ] 备份文件可访问

## Dify 集成检查

### 1. 环境变量配置

在 Dify 中：

- [ ] 已添加 `LITERATURE_API_KEY` 环境变量
- [ ] API Key 值正确

### 2. Workflow 配置

- [ ] HTTP Request 节点已配置
- [ ] API 端点 URL 正确
- [ ] Headers 包含 API Key
- [ ] 请求体格式正确

### 3. 集成测试

- [ ] 可以从 Dify 触发下载
- [ ] 任务状态查询正常
- [ ] 文件下载成功
- [ ] 错误处理正常

## 性能优化检查

### 1. 资源配置

- [ ] Worker 数量已优化（`APP_WORKERS`）
- [ ] Celery 并发数已优化（`CELERY_WORKER_CONCURRENCY`）
- [ ] 数据库连接池已配置
- [ ] Redis 内存限制已设置

### 2. 扩展配置

```bash
# 如需要，扩展 worker
docker-compose -f docker-compose.prod.yml up -d --scale celery=3
```

- [ ] 根据负载调整了 worker 数量
- [ ] 负载均衡已配置（如使用多个 API 实例）

## 监控和维护

### 1. 日常监控

- [ ] 每日检查服务状态
- [ ] 每日检查日志错误
- [ ] 每周检查磁盘使用
- [ ] 每周检查数据库大小

### 2. 定期维护

- [ ] 每月清理旧任务记录
- [ ] 每月清理旧文件
- [ ] 每季度更新依赖包
- [ ] 每季度审查安全配置

### 3. 监控命令

```bash
# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f

# 查看资源使用
docker stats

# 查看磁盘使用
df -h
du -sh /var/lib/docker/volumes/*
```

## 故障恢复

### 1. 服务重启

```bash
# 重启所有服务
docker-compose -f docker-compose.prod.yml restart

# 重启特定服务
docker-compose -f docker-compose.prod.yml restart app
docker-compose -f docker-compose.prod.yml restart celery
```

### 2. 数据恢复

```bash
# 恢复数据库
make restore-db FILE=backups/backup_20231201.sql

# 恢复 MinIO 数据
mc mirror /backup/minio/ minio/literature-papers
```

### 3. 回滚

```bash
# 停止服务
docker-compose -f docker-compose.prod.yml down

# 恢复旧版本代码
git checkout <previous-version>

# 重新部署
./scripts/deploy.sh
```

## 文档和培训

- [ ] 团队成员已了解部署流程
- [ ] 运维文档已更新
- [ ] 故障处理流程已文档化
- [ ] 联系人信息已更新

## 最终检查

- [ ] 所有上述检查项已完成
- [ ] 服务运行稳定（至少 24 小时）
- [ ] 性能满足要求
- [ ] 备份和恢复已测试
- [ ] 监控告警正常工作
- [ ] 团队已准备好处理问题

## 签署确认

- 部署人员: ******\_\_\_\_******
- 日期: ******\_\_\_\_******
- 审核人员: ******\_\_\_\_******
- 日期: ******\_\_\_\_******

---

**注意**:

- 请在每个检查项完成后打勾 ✓
- 如有任何问题，请参考 [DEPLOYMENT.md](./DEPLOYMENT.md)
- 紧急情况联系: [联系方式]

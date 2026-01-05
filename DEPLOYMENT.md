# 生产环境部署与配置手册

## 文档版本
- 版本：1.0.0
- 更新日期：2026.1.1
- 适用环境：生产环境 (Production Environment)

---

## 目录

1. [环境预要求](#1-环境预要求)
2. [基础架构概览](#2-基础架构概览)
3. [关键组件配置清单](#3-关键组件配置清单)
4. [服务部署步骤](#4-服务部署步骤)
5. [数据持久化](#5-数据持久化)
6. [配置文件详解](#6-配置文件详解)


---

## 1. 环境预要求

### 1.1 服务器配置

**推荐配置（小型部署）：**
- **CPU**: 4 核心
- **内存**: 8GB RAM
- **磁盘**: 100GB 可用空间（SSD 推荐）
- **网络**: 100Mbps 或更高

**最低配置：**
- **CPU**: 2 核心
- **内存**: 4GB RAM
- **磁盘**: 50GB 可用空间
- **网络**: 10Mbps

### 1.2 操作系统要求

- **推荐**: Ubuntu 22.04 LTS 或更高版本
- **内核版本**: Linux 5.4+（支持 Docker）

### 1.3 软件依赖

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| Docker | 20.10+ | 容器运行时 |
| Docker Compose | 2.0+ | 容器编排工具 |
| Git | 2.0+ | 代码版本控制 |

### 1.4 网络端口要求

**必须开放的端口：**

| 端口 | 服务 | 说明 |
|------|------|------|
| 3000 | Frontend | 前端应用 |
| 8000 | Nexus | 工作流编排服务 |
| 8001 | Download Service | 下载服务 API |
| 8002 | Translator Service | 翻译服务 |
| 8003 | Retrieval Service | 检索服务 |
| 8005 | Application Service | 应用服务 API |
| 8020 | Indexing Service | 索引服务 API |
| 8031 | Parser Service | 解析服务 API |
| 8040 | Overview Service | 概览服务 API |
| 9000 | MinIO API | 对象存储 API |
| 9001 | MinIO Console | MinIO 管理控制台 |
| 15672 | RabbitMQ Management | RabbitMQ 管理界面 |
| 3306 | MySQL | 数据库（如果从外部访问） |
| 5432 | PostgreSQL (downloads) | 数据库 |
| 5434 | PostgreSQL (discovery) | 数据库 |
| 5435 | PostgreSQL (parser) | 数据库 |
| 5436 | PostgreSQL (indexing) | 数据库 |
| 6379 | Redis | 缓存服务 |
| 5672 | RabbitMQ | 消息队列 |

---

## 2. 基础架构概览

### 2.1 系统架构图

```mermaid
graph TB
    subgraph External["外部访问"]
        User[用户浏览器]
        MySQL_External[MySQL 外部服务器<br/>101.132.102.157:3306]
    end
    
    subgraph Docker_Network["Docker 网络"]
        subgraph Infrastructure["基础设施层"]
            RabbitMQ[RabbitMQ<br/>消息队列<br/>:5672]
            MinIO[MinIO<br/>对象存储<br/>:9000]
            Redis[Redis<br/>缓存<br/>:6379]
            PG_Downloads[PostgreSQL<br/>downloads<br/>:5432]
            PG_Discovery[PostgreSQL<br/>discovery<br/>:5434]
            PG_Parser[PostgreSQL<br/>parser<br/>:5435]
            PG_Indexing[PostgreSQL<br/>indexing<br/>:5436]
        end
        
        subgraph Core_Services["核心服务层"]
            Nexus[Nexus<br/>工作流编排<br/>:8000]
        end
        
        subgraph Tool_Services["工具服务层"]
            Discovery[Discovery Service<br/>发现服务]
            Download_API[Download Service API<br/>:8001]
            Download_Worker[Download Worker]
            Parser_API[Parser Service API<br/>:8031]
            Parser_Worker[Parser Worker]
            Indexing_API[Indexing Service API<br/>:8020]
            Indexing_Worker[Indexing Worker]
            Overview_API[Overview Service API<br/>:8040]
            Overview_Worker[Overview Worker]
            Retrieval[Retrieval Service<br/>:8003]
            Translator[Translator Service<br/>:8002]
        end
        
        subgraph App_Services["应用服务层"]
            App_Service[Application Service<br/>:8005]
            Frontend[Frontend<br/>Nginx<br/>:3000]
        end
    end
    
    User -->|HTTP| Frontend
    Frontend -->|HTTP| App_Service
    App_Service -->|HTTP| Translator
    App_Service -->|HTTP| Indexing_API
    App_Service -->|HTTP| Download_API
    App_Service -->|MySQL| MySQL_External
    
    Nexus -->|AMQP| RabbitMQ
    Nexus -->|S3| MinIO
    Discovery -->|AMQP| RabbitMQ
    Discovery -->|PostgreSQL| PG_Discovery
    Download_API -->|PostgreSQL| PG_Downloads
    Download_API -->|Redis| Redis
    Download_API -->|S3| MinIO
    Parser_API -->|PostgreSQL| PG_Parser
    Parser_API -->|AMQP| RabbitMQ
    Parser_API -->|S3| MinIO
    Indexing_API -->|PostgreSQL| PG_Indexing
    Indexing_API -->|AMQP| RabbitMQ
    Indexing_API -->|S3| MinIO
    Overview_API -->|AMQP| RabbitMQ
    Overview_API -->|S3| MinIO
    Retrieval -->|AMQP| RabbitMQ
    Retrieval -->|S3| MinIO
    Translator -->|AMQP| RabbitMQ
    Translator -->|S3| MinIO
```

### 2.2 服务分类

**基础设施服务：**
- RabbitMQ: 消息队列
- MinIO: 对象存储
- Redis: 缓存服务
- PostgreSQL: 数据库（4个实例）
- MySQL: 数据库（外部服务器）

**核心服务：**
- Nexus: 工作流编排引擎

**工具服务：**
- Discovery Service: 文献发现服务
- Download Service: 文献下载服务（API + Worker）
- Parser Service: 文献解析服务（API + Worker）
- Indexing Service: 文献索引服务（API + Worker）
- Overview Service: 文献概览生成服务（API + Worker）
- Retrieval Service: 统一检索服务
- Translator Service: 文献翻译服务

**应用服务：**
- Application Service: 应用后端 API
- Frontend: 前端应用（Vue + Nginx）

### 2.3 服务依赖关系

```
Frontend
  └── depends_on: Application Service

Application Service
  └── depends_on: MySQL (外部), Translator Service, Indexing Service API, Download Service API

Nexus
  └── depends_on: RabbitMQ, MinIO

Discovery Service
  └── depends_on: RabbitMQ, MinIO, Discovery PostgreSQL

Download Service
  └── depends_on: Downloads PostgreSQL, Redis, MinIO

Parser Service
  └── depends_on: Parser PostgreSQL, RabbitMQ, MinIO, Download Service API

Indexing Service
  └── depends_on: Indexing PostgreSQL, RabbitMQ, MinIO, Parser Service API

Overview Service
  └── depends_on: RabbitMQ, MinIO

Retrieval Service
  └── depends_on: RabbitMQ, MinIO

Translator Service
  └── depends_on: RabbitMQ, MinIO
```

---

## 3. 关键组件配置清单

### 3.1 数据库配置

| 组件 | 类型 | 主机地址 | 端口 | 数据库名 | 用户名 | 密码 | 说明 |
|------|------|---------|------|---------|--------|------|------|
| MySQL | MySQL 8.0 | 101.132.102.157 | 3306 | wfw_db | app_user | WFWwfw123... | 外部服务器，Application Service 使用 |
| PostgreSQL | PostgreSQL 15 | localhost (docker) | 5432 | downloads | user | WFWwfw123... | Download Service 使用 |
| PostgreSQL | PostgreSQL 15 | localhost (docker) | 5434 | discovery | discovery_user | WFWwfw123... | Discovery Service 使用 |
| PostgreSQL | PostgreSQL 15 | localhost (docker) | 5435 | parser | parser_user | WFWwfw123... | Parser Service 使用 |
| PostgreSQL | PostgreSQL 15 | localhost (docker) | 5436 | indexing | index_user | WFWwfw123... | Indexing Service 使用 |

### 3.2 中间件配置

| 组件 | 类型 | 主机地址 | 端口 | 用户名 | 密码 | 说明 |
|------|------|---------|------|--------|------|------|
| RabbitMQ | RabbitMQ 3.9 | localhost (docker) | 5672 | guest | WFWwfw123... | 消息队列 |
| RabbitMQ Management | RabbitMQ 3.9 | localhost (docker) | 15672 | guest | WFWwfw123... | 管理界面 |
| MinIO | MinIO | localhost (docker) | 9000 | minioadmin | minioadmin | 对象存储 API |
| MinIO Console | MinIO | localhost (docker) | 9001 | minioadmin | minioadmin | 管理控制台 |
| Redis | Redis 7 | localhost (docker) | 6379 | - | WFWwfw123... | 缓存服务 |

### 3.3 服务端点配置

| 服务 | 内部地址 | 外部端口 | 健康检查端点 | 说明 |
|------|---------|---------|-------------|------|
| Frontend | http://frontend:80 | 3000 | http://localhost:3000 | 前端应用 |
| Application Service | http://application_service:8000 | 8005 | http://localhost:8005/health | 应用后端 |
| Nexus | http://nexus:8000 | 8000 | http://localhost:8000/api/v1/health | 工作流编排 |
| Download Service | http://download_service_api:8000 | 8001 | http://localhost:8001/health | 下载服务 |
| Translator Service | http://translator_service:8002 | 8002 | http://localhost:8002/health | 翻译服务 |
| Retrieval Service | http://retrieval_service:8003 | 8003 | http://localhost:8003/health | 检索服务 |
| Indexing Service | http://indexing_service_api:8020 | 8020 | http://localhost:8020/health/ready | 索引服务 |
| Parser Service | http://parser_service_api:8031 | 8031 | http://localhost:8031/health | 解析服务 |
| Overview Service | http://overview_service_api:8040 | 8040 | http://localhost:8040/health | 概览服务 |

---

## 4. 服务部署步骤

本系统使用 **GitHub Actions CI/CD** 实现自动化构建和部署。代码推送到仓库后，GitHub Actions 会自动构建 Docker 镜像并部署到生产服务器。

### 4.1 部署方案概述

**部署流程：**

```
GitHub 仓库:
  1. 代码推送触发工作流
  2. GitHub Actions 构建所有 Docker 镜像
  3. 保存镜像为 tar.gz 文件
  4. 打包配置文件
  5. 上传部署包到生产服务器

生产服务器:
  1. 接收部署包
  2. 解压并加载 Docker 镜像
  3. 启动服务
  4. 执行健康检查
```


### 4.2 前置要求

#### 4.2.1 GitHub 仓库设置

1. **确保代码已推送到 GitHub 仓库**
2. **确保有仓库的管理权限**（用于配置 Secrets）

#### 4.2.2 服务器 SSH 配置

在生产服务器上配置 SSH 密钥认证：

```bash
# 在本地生成 SSH 密钥对（如果还没有）
ssh-keygen -t rsa -b 4096 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy

# 将公钥添加到服务器的 authorized_keys
ssh-copy-id -i ~/.ssh/github_actions_deploy.pub root@8.134.183.68

```

#### 4.2.3 服务器目录准备

在服务器上创建部署目录：

```bash
# SSH 连接到服务器
ssh root@8.134.183.68

# 创建部署目录
mkdir -p ~/myapp
mkdir -p ~/myapp/images
mkdir -p ~/myapp/config
mkdir -p ~/myapp/backups
```

### 4.3 GitHub Secrets 配置

GitHub Secrets 用于安全存储敏感信息。配置步骤如下：

#### 4.3.1 访问 Secrets 配置页面

1. 打开 GitHub 仓库页面
2. 点击 **Settings**（设置）
3. 在左侧菜单选择 **Secrets and variables** → **Actions**
4. 点击 **New repository secret**（新建仓库密钥）

#### 4.3.2 配置必需的 Secrets

需要配置以下 Secrets：

**1. SERVER_IP**
- **Name**: `SERVER_IP`
- **Value**: `8.134.183.68`
- **说明**: 生产服务器 IP 地址

**2. SERVER_USER**
- **Name**: `SERVER_USER`
- **Value**: `root`
- **说明**: 服务器 SSH 用户名

**3. SSH_PRIVATE_KEY**
- **Name**: `SSH_PRIVATE_KEY`
- **Value**: 之前生成的 SSH 私钥完整内容
- **说明**: 用于 SSH 连接到服务器的私钥
- **获取方式**:
  ```bash
  # 在本地查看私钥内容
  cat ~/.ssh/github_actions_deploy
  # 复制完整内容（包括 -----BEGIN 和 -----END 行）
  ```

**4. REMOTE_PATH**
- **Name**: `REMOTE_PATH`
- **Value**: `~/myapp`
- **说明**: 服务器上的部署路径

**5. VITE_API_BASE_URL**
- **Name**: `VITE_API_BASE_URL`
- **Value**: `http://8.134.183.68:8005/api/v1`
- **说明**: 前端构建时使用的 API 地址（用户浏览器访问的地址）

**6. VITE_MINIO_UPLOAD_URL**
- **Name**: `VITE_MINIO_UPLOAD_URL`
- **Value**: `http://8.134.183.68:8001/upload`
- **说明**: 前端构建时使用的 MinIO 上传地址

**7. ENV_PROD**
- **Name**: `ENV_PROD`
- **Value**: `.env.prod` 文件的完整内容
- **说明**: 生产环境变量配置

#### 4.3.3 Secrets 配置示例

以下是配置 Secrets 的完整示例：

**Secrets 配置清单：**

| Secret 名称 | 值 | 说明 |
|------------|-----|------|
| `SERVER_IP` | `8.134.183.68` | 生产服务器 IP 地址 |
| `SERVER_USER` | `root` | 服务器 SSH 用户名 |
| `SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----<br/>b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABlwAAAAdzc2gtcn<br/><br/>-----END OPENSSH PRIVATE KEY-----` | SSH 私钥（完整内容，包括 BEGIN 和 END 行） |
| `REMOTE_PATH` | `~/myapp` | 服务器部署路径（可选） |
| `VITE_API_BASE_URL` | `http://8.134.183.68:8005/api/v1` | 前端 API 地址 |
| `VITE_MINIO_UPLOAD_URL` | `http://8.134.183.68:8001/upload` | MinIO 上传地址 |
| `ENV_PROD` | （见下方示例） | 环境变量文件内容（可选） |

**ENV_PROD Secret 示例内容：**

`.env.prod` 文件内容：

```env
# MySQL 数据库配置（外部服务器）
MYSQL_HOST=101.132.102.157
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=WFWwfw123...
MYSQL_DATABASE=wfw_db
MYSQL_USER=app_user
MYSQL_PASSWORD=WFWwfw123...

# Application Service 配置
APPLICATION_DATABASE_URL=mysql+pymysql://app_user:WFWwfw123...@101.132.102.157:3306/wfw_db?charset=utf8mb4
DB_HOST=101.132.102.157
DB_PORT=3306
DB_USER=app_user
DB_PASSWORD=WFWwfw123...
DB_NAME=wfw_db
APPLICATION_SERVICE_PORT=8005
APPLICATION_API_BASE_URL=http://application_service:8000/api/v1
APPLICATION_BASE_HOST=http://application_service:8000

# 外部服务 URL 配置（Docker 内部网络）
TRANSLATOR_SERVICE_BASE_URL=http://translator_service:8002
INDEXING_SERVICE_BASE_URL=http://indexing_service_api:8020
MINIO_UPLOAD_URL=http://download_service_api:8000/upload

# Frontend 配置
FRONTEND_PORT=3000
VITE_API_BASE_URL=http://8.134.183.68:8005/api/v1
VITE_MINIO_UPLOAD_URL=http://8.134.183.68:8001/upload
```


### 4.4 工作流配置说明

工作流配置文件位于 `.github/workflows/build-and-deploy.yml`，包含以下主要部分：

#### 4.4.1 触发条件

工作流在以下情况触发：

1. **手动触发**（推荐用于首次部署和测试）
   - 在 GitHub 仓库页面，点击 **Actions** 标签
   - 选择 **Build and Deploy to Production** 工作流
   - 点击 **Run workflow**，可以指定版本号和选择是否跳过部署

2. **推送到主分支**
   - 推送到 `main` 或 `master` 分支时自动触发
   - 适合持续集成场景

3. **创建 Release Tag**
   - 创建以 `v` 开头的 tag（如 `v1.0.0`）时触发
   - 适合正式版本发布

#### 4.4.2 构建步骤详解

工作流包含两个主要 Job：

**Job 1: build（构建 Docker 镜像）**

步骤说明：

1. **检出代码**
   ```yaml
   - uses: actions/checkout@v4
   ```
   - 从 GitHub 仓库检出代码到工作流运行环境

2. **设置版本号**
   - 如果手动触发并指定了版本号，使用指定版本
   - 如果是 tag 触发，使用 tag 名称作为版本
   - 否则使用时间戳和 Git SHA 作为版本

3. **设置 Docker Buildx**
   ```yaml
   - uses: docker/setup-buildx-action@v3
   ```
   - 配置 Docker Buildx 以支持高级构建功能
   - 启用构建缓存以加速后续构建

4. **构建各个服务镜像**
   - 使用 `docker/build-push-action@v5` 构建每个服务的镜像
   - 每个镜像都打上版本标签和 `latest` 标签
   - 使用 GitHub Actions 缓存加速构建

5. **保存镜像为 tar.gz 文件**
   ```bash
   docker save <image>:<version> | gzip > build/images/<service>_<version>.tar.gz
   ```
   - 将每个镜像保存为压缩的 tar 文件
   - 文件存储在 `build/images/` 目录

6. **复制配置文件**
   - 复制 `docker-compose.yml` 到 `build/config/`
   - 复制 `env.prod.example` 到 `build/config/`
   - 复制 `scripts/server-deploy.sh` 到 `build/config/`

7. **创建版本信息和清单**
   - 生成 `VERSION` 文件，包含版本、构建时间、Git 信息
   - 生成 `MANIFEST` 文件，列出所有镜像和配置文件

8. **打包部署包**
   ```bash
   tar -czf deployment-package-<version>.tar.gz images/ config/ VERSION MANIFEST
   ```

9. **上传为 Artifact**
   - 将部署包上传为 GitHub Actions Artifact
   - 保留 30 天，可用于下载和回滚

**Job 2: deploy（部署到生产服务器）**

步骤说明：

1. **下载部署包**
   - 从 build job 的 Artifact 下载部署包

2. **配置 SSH**
   ```bash
   echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/deploy_key
   chmod 600 ~/.ssh/deploy_key
   ssh-keyscan -H $SERVER_IP >> ~/.ssh/known_hosts
   ```
   - 将 SSH 私钥写入文件并设置权限
   - 将服务器公钥添加到 known_hosts

3. **测试服务器连接**
   - 验证 SSH 连接是否正常

4. **在服务器上创建目录**
   - 确保部署目录结构存在

5. **上传部署包**
   ```bash
   scp deployment-package-*.tar.gz root@8.134.183.68:~/myapp/
   ```

6. **在服务器上解压部署包**
   ```bash
   cd ~/myapp
   tar -xzf deployment-package-*.tar.gz
   ```

7. **上传环境变量文件**（如果配置了 ENV_PROD Secret）
   - 将 `.env.prod` 文件上传到服务器

8. **执行服务器端部署**
   - 运行 `server-deploy.sh` 脚本
   - 脚本会加载镜像、启动服务、执行健康检查

9. **健康检查**
   - 等待 30 秒后检查服务健康状态

### 4.5 部署流程

#### 4.5.1 首次部署

**步骤 1: 配置 GitHub Secrets**

按照 [4.3 GitHub Secrets 配置](#43-github-secrets-配置) 章节配置所有必需的 Secrets。

**步骤 2: 在服务器上创建环境变量文件**

```bash
# SSH 连接到服务器
ssh root@8.134.183.68

# 进入部署目录
mkdir -p ~/myapp/config
cd ~/myapp/config

```

**步骤 3: 手动触发工作流**

1. 打开 GitHub 仓库页面
2. 点击 **Actions** 标签
3. 选择 **Build and Deploy to Production** 工作流
4. 点击 **Run workflow**
5. 选择分支（通常是 `main`）
6. 点击 **Run workflow** 按钮

**步骤 4: 监控部署过程**

1. 在工作流运行页面查看实时日志
2. 等待构建完成
3. 等待部署完成


#### 4.5.2 自动部署（推送到主分支）

配置完成后，每次推送到 `main`  分支都会自动触发部署：

```bash
# 本地提交代码
git add .
git commit -m "更新功能"
git push origin main

# GitHub Actions 会自动触发构建和部署
```

#### 4.5.3 版本发布部署

创建 Release Tag 触发部署：

```bash
# 创建并推送 tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# GitHub Actions 会自动触发构建和部署，版本号为 v1.0.0
```

### 4.6 验证部署

#### 4.6.1 查看工作流状态

1. 在 GitHub 仓库页面点击 **Actions** 标签
2. 查看最新的工作流运行状态
3. 点击运行记录查看详细日志

#### 4.6.2 验证服务器服务

```bash
# SSH 连接到服务器
ssh root@8.134.183.68

# 查看服务状态
cd ~/myapp
docker-compose -f config/docker-compose.yml --env-file config/.env.prod ps

# 检查服务健康状态
curl http://localhost:8005/health
curl http://localhost:3000

# 查看服务日志
docker-compose -f config/docker-compose.yml --env-file config/.env.prod logs -f
```

#### 4.6.3 验证外部访问

```bash
# 从外部访问
curl http://8.134.183.68:8005/health
curl http://8.134.183.68:3000

# 访问 API 文档
# 浏览器打开: http://8.134.183.68:8005/docs
```

### 4.7 回滚操作

如果需要回滚到之前的版本：

#### 方式一：使用 GitHub Actions Artifact

1. 在 GitHub 仓库页面点击 **Actions** 标签
2. 找到之前成功部署的工作流运行
3. 下载 `deployment-package` Artifact
4. 手动上传到服务器并部署

#### 方式二：服务器端回滚

```bash
# SSH 连接到服务器
ssh root@8.134.183.68

# 进入部署目录
cd ~/myapp

# 停止当前服务
docker-compose -f config/docker-compose.yml --env-file config/.env.prod down

# 查看备份
ls -lh backups/

# 恢复备份的配置（如果需要）
cp backups/YYYYMMDD_HHMMSS/.env.prod.backup config/.env.prod

# 如果有旧版本的镜像文件，可以加载
# docker load < backups/YYYYMMDD_HHMMSS/images/*.tar.gz

# 重新部署
./config/server-deploy.sh
```



## 5. 数据持久化

### 5.1 Docker Volumes 清单

| Volume 名称 | 用途 | 数据位置 |
|------------|------|---------|
| `minio_data` | MinIO 对象存储数据 | `/var/lib/docker/volumes/<project>_minio_data` |
| `postgres_data` | Downloads 数据库数据 | `/var/lib/docker/volumes/<project>_postgres_data` |
| `discovery_postgres_data` | Discovery 数据库数据 | `/var/lib/docker/volumes/<project>_discovery_postgres_data` |
| `parser_postgres_data` | Parser 数据库数据 | `/var/lib/docker/volumes/<project>_parser_postgres_data` |
| `indexing_postgres_data` | Indexing 数据库数据 | `/var/lib/docker/volumes/<project>_indexing_postgres_data` |
| `indexing_chroma_data` | Chroma 向量数据库数据 | `/var/lib/docker/volumes/<project>_indexing_chroma_data` |
| `mysql_data` | MySQL 数据库数据（如果使用容器） | `/var/lib/docker/volumes/<project>_mysql_data` |
| `application_uploads` | 应用上传文件 | `/var/lib/docker/volumes/<project>_application_uploads` |

### 5.2 备份策略

#### 5.2.1 数据库备份

```bash
# PostgreSQL 备份
docker-compose exec db pg_dump -U user downloads > backup_downloads_$(date +%Y%m%d).sql
docker-compose exec discovery_db pg_dump -U discovery_user discovery > backup_discovery_$(date +%Y%m%d).sql
docker-compose exec parser_db pg_dump -U parser_user parser > backup_parser_$(date +%Y%m%d).sql
docker-compose exec indexing_db pg_dump -U index_user indexing > backup_indexing_$(date +%Y%m%d).sql

# MySQL 备份（外部服务器）
mysqldump -h 101.132.102.157 -u app_user -pWFWwfw123... wfw_db > backup_mysql_$(date +%Y%m%d).sql
```

#### 5.2.2 Volume 备份

```bash
# 备份所有 volumes
docker run --rm -v <project>_minio_data:/data -v $(pwd):/backup alpine tar czf /backup/minio_data_backup_$(date +%Y%m%d).tar.gz /data
docker run --rm -v <project>_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data_backup_$(date +%Y%m%d).tar.gz /data
```

### 5.3 数据恢复

```bash
# PostgreSQL 恢复
docker-compose exec -T db psql -U user downloads < backup_downloads_20240101.sql

# MySQL 恢复
mysql -h 101.132.102.157 -u app_user -pWFWwfw123... wfw_db < backup_mysql_20240101.sql

# Volume 恢复
docker run --rm -v <project>_minio_data:/data -v $(pwd):/backup alpine tar xzf /backup/minio_data_backup_20240101.tar.gz -C /
```

---

## 6. 配置文件详解

本章节详细说明部署过程中涉及的关键配置文件的结构和重点配置项。

### 6.1 docker-compose.yml 配置说明

**文件位置**: 项目根目录  
**用途**: 定义所有服务的容器编排配置

#### 6.1.1 文件结构概览

配置文件主要包含以下部分：

1. **基础设施服务**（Infrastructure）
   - RabbitMQ: 消息队列服务
   - MinIO: 对象存储服务
   - Redis: 缓存服务
   - PostgreSQL: 数据库服务（4个实例）

2. **核心服务**（Core Services）
   - Nexus: 工作流编排引擎

3. **工具服务**（Tool Services）
   - Discovery Service: 发现服务（API + Worker）
   - Download Service: 下载服务（API + Worker + MQ Worker）
   - Parser Service: 解析服务（API + Worker + Migrations）
   - Indexing Service: 索引服务（API + Worker + Migrations）
   - Overview Service: 概览服务（API + Worker）
   - Retrieval Service: 检索服务
   - Translator Service: 翻译服务

4. **应用服务**（App Services）
   - Application Service: 应用后端 API
   - Frontend: 前端应用（Nginx）

#### 6.1.2 关键配置项说明

**服务依赖关系**:
```yaml
depends_on:
  rabbitmq:
    condition: service_healthy
  minio:
    condition: service_healthy
```
- 使用 `service_healthy` 条件确保依赖服务健康后才启动

**端口映射**:
```yaml
ports:
  - "8005:8000"  # 外部端口:容器内部端口
```

**环境变量**:
- 所有敏感信息（密码、密钥）通过环境变量文件（`.env.prod`）注入
- 服务间通信使用 Docker 内部网络地址（如 `rabbitmq:5672`）

**数据持久化**:
```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
  - minio_data:/data
```

**健康检查**:
```yaml
healthcheck:
  test: ["CMD", "rabbitmqctl", "status"]
  interval: 10s
  timeout: 5s
  retries: 5
```

#### 6.1.3 重要注意事项

- **MySQL 数据库**: 配置中使用外部 MySQL 服务器（`101.132.102.157:3306`），不在 Docker Compose 中定义
- **服务网络**: 所有服务默认加入同一 Docker 网络，可通过服务名互相访问
- **资源限制**: 生产环境建议添加 `deploy.resources` 限制 CPU 和内存使用

---

### 6.2 环境变量配置文件（.env.prod）

**文件位置**: 项目根目录（从 `env.prod.example` 复制）  
**用途**: 存储所有服务的环境变量配置

#### 6.2.1 配置分类

**1. 基础设施配置**
```env
# RabbitMQ
RABBITMQ_DEFAULT_USER=guest
RABBITMQ_DEFAULT_PASS=WFWwfw123...

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# Redis
REDIS_PASSWORD=WFWwfw123...
REDIS_URL=redis://:WFWwfw123...@redis:6379/0
```

**2. 数据库配置**
```env
# MySQL（外部服务器）
MYSQL_HOST=101.132.102.157
MYSQL_PORT=3306
MYSQL_DATABASE=wfw_db
MYSQL_USER=app_user
MYSQL_PASSWORD=WFWwfw123...

# PostgreSQL（4个实例）
POSTGRES_DB_DOWNLOADS=downloads
POSTGRES_USER_DOWNLOADS=user
POSTGRES_PASSWORD_DOWNLOADS=WFWwfw123...
# ... discovery, parser, indexing 类似配置
```

**3. 服务 URL 配置（Docker 内部网络）**
```env
TRANSLATOR_SERVICE_BASE_URL=http://translator_service:8002
INDEXING_SERVICE_BASE_URL=http://indexing_service_api:8020
MINIO_UPLOAD_URL=http://download_service_api:8000/upload
```

**4. 前端构建配置（外部访问地址）**
```env
# 注意：这些是用户浏览器访问的地址，必须是外部可访问的
VITE_API_BASE_URL=http://8.134.183.68:8005/api/v1
VITE_MINIO_UPLOAD_URL=http://8.134.183.68:8001/upload
```

#### 6.2.2 关键配置说明

| 配置项 | 说明 | 注意事项 |
|--------|------|---------|
| `MYSQL_HOST` | MySQL 服务器地址 | 外部服务器，确保网络可达 |
| `VITE_API_BASE_URL` | 前端 API 地址 | **必须是外部可访问地址**，构建时注入到前端代码 |
| `VITE_MINIO_UPLOAD_URL` | MinIO 上传地址 | **必须是外部可访问地址** |
| 服务间 URL | 使用 Docker 服务名 | 如 `http://translator_service:8002` |
| `SILICONFLOW2_API_KEY` | AI 服务密钥 | 可选，用于概览生成功能 |

#### 6.2.3 配置步骤

1. 复制模板文件: `cp env.prod.example .env.prod`
2. 修改关键配置:
   - 替换所有 `WFWwfw123...` 为强密码
   - 修改 `VITE_API_BASE_URL` 为实际服务器 IP 或域名
   - 修改 `VITE_MINIO_UPLOAD_URL` 为实际服务器 IP 或域名
3. 验证配置: 确保所有必需配置项已填写

---

### 6.3 服务器部署脚本（server-deploy.sh）

**文件位置**: `scripts/server-deploy.sh`  
**用途**: 在服务器上执行自动化部署流程

#### 6.3.1 脚本主要功能

脚本按以下顺序执行：

1. **环境检查**
   - 检查 Docker 和 Docker Compose 是否安装
   - 验证必要文件是否存在

2. **备份现有服务**
   - 如果检测到运行中的服务，自动创建备份
   - 备份目录: `backups/YYYYMMDD_HHMMSS/`

3. **加载 Docker 镜像**
   - 从 `images/` 目录加载所有 `.tar.gz` 镜像文件
   - 使用 `docker load` 命令加载

4. **启动基础设施服务**
   - 按顺序启动: RabbitMQ → MinIO → Redis → PostgreSQL
   - 等待服务健康检查通过

5. **执行数据库迁移**
   - Discovery Service 迁移
   - Parser Service 迁移
   - Indexing Service 迁移

6. **启动所有服务**
   - 使用 `docker-compose up -d` 启动所有服务

7. **健康检查**
   - 检查 Application Service (`http://localhost:8005/health`)
   - 检查 Frontend (`http://localhost:3000`)
   - 最多重试 30 次，每次间隔 5 秒

#### 6.3.2 关键配置变量

```bash
IMAGES_DIR="${PROJECT_DIR}/images"      # 镜像文件目录
CONFIG_DIR="${SCRIPT_DIR}"              # 配置文件目录
COMPOSE_FILE="${CONFIG_DIR}/docker-compose.yml"
ENV_FILE="${CONFIG_DIR}/.env.prod"
```

#### 6.3.3 使用方法

```bash
# 在服务器上执行
cd ~/myapp
./config/server-deploy.sh
```

#### 6.3.4 错误处理

- 脚本使用 `set -e`，任何命令失败都会立即退出
- 提供彩色日志输出（INFO/WARN/ERROR）
- 失败时显示详细的错误信息和排查建议

---

### 6.4 Nginx 配置（frontend/nginx.conf）

**文件位置**: `frontend/nginx.conf`  
**用途**: 前端 Nginx 服务器配置，处理静态资源和 API 代理

#### 6.4.1 主要配置模块

**1. 基础配置**
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
}
```

**2. Gzip 压缩**
```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript;
```
- 启用 Gzip 压缩，减少传输大小

**3. 安全头设置**
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
```

**4. API 代理配置**
```nginx
location /api/ {
    proxy_pass http://application_service:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```
- 将 `/api/` 请求代理到 Application Service
- 使用 Docker 服务名 `application_service` 进行内部通信

**5. SPA 路由支持**
```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```
- 支持 Vue.js 等 SPA 框架的前端路由

**6. 静态资源缓存**
```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

#### 6.4.2 关键配置说明

| 配置项 | 说明 | 注意事项 |
|--------|------|---------|
| `proxy_pass` | 后端服务地址 | 使用 Docker 服务名，如 `application_service:8000` |
| `try_files` | SPA 路由支持 | 确保所有前端路由都返回 `index.html` |
| 超时设置 | 代理超时配置 | `proxy_read_timeout 60s` 可根据需要调整 |

---

### 6.5 GitHub Actions 工作流配置

**文件位置**: `.github/workflows/build-and-deploy.yml`  
**用途**: 自动化构建和部署流程

#### 6.5.1 工作流触发条件

```yaml
on:
  # 手动触发
  workflow_dispatch:
    inputs:
      version: '部署版本号'
      skip_deploy: '仅构建，不部署'
  
  # 推送到主分支
  push:
    branches: [main, master]
  
  # 创建 release tag
  push:
    tags: ['v*']
```

#### 6.5.2 构建流程（build job）

**主要步骤**:

1. **设置版本号**
   - 手动指定版本 → 使用指定版本
   - Tag 触发 → 使用 tag 名称
   - 其他情况 → 使用时间戳 + Git SHA

2. **构建 Docker 镜像**
   - 使用 `docker/build-push-action@v5` 构建所有服务镜像
   - 启用 GitHub Actions 缓存加速构建
   - 镜像标签: `<service>:<version>` 和 `<service>:latest`

3. **保存镜像为 tar.gz**
   ```bash
   docker save <image>:<version> | gzip > build/images/<service>_<version>.tar.gz
   ```

4. **复制配置文件**
   - `docker-compose.yml`
   - `env.prod.example`
   - `scripts/server-deploy.sh`

5. **创建版本信息**
   - `VERSION`: 版本、构建时间、Git 信息
   - `MANIFEST`: 镜像和配置文件清单

6. **打包部署包**
   ```bash
   tar -czf deployment-package-<version>.tar.gz images/ config/ VERSION MANIFEST
   ```

#### 6.5.3 部署流程（deploy job）

**主要步骤**:

1. **配置 SSH 连接**
   ```bash
   echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/deploy_key
   ssh-keyscan -H $SERVER_IP >> ~/.ssh/known_hosts
   ```

2. **上传部署包到服务器**
   ```bash
   scp deployment-package-*.tar.gz root@8.134.183.68:~/myapp/
   ```

3. **在服务器上解压并部署**
   ```bash
   cd ~/myapp
   tar -xzf deployment-package-*.tar.gz
   ./config/server-deploy.sh
   ```

4. **健康检查**
   - 等待 30 秒后检查服务健康状态

#### 6.5.4 关键环境变量

从 GitHub Secrets 读取:
- `SERVER_IP`: 生产服务器 IP
- `SERVER_USER`: SSH 用户名
- `SSH_PRIVATE_KEY`: SSH 私钥
- `VITE_API_BASE_URL`: 前端 API 地址
- `VITE_MINIO_UPLOAD_URL`: MinIO 上传地址
- `ENV_PROD`: 环境变量文件内容（可选）

#### 6.5.5 重要注意事项

- **构建缓存**: 使用 GitHub Actions 缓存加速后续构建
- **Artifact 保留**: 部署包保留 30 天，可用于回滚
- **跳过部署**: 可通过 `skip_deploy` 参数仅构建不部署
- **版本管理**: 建议使用语义化版本号（如 `v1.0.0`）

---

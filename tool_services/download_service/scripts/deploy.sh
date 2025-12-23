#!/bin/bash

# ============================================
# 生产环境部署脚本
# ============================================

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查必要的工具
check_requirements() {
    log_info "检查部署环境..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    log_info "环境检查通过"
}

# 检查环境变量文件
check_env_file() {
    log_info "检查环境配置文件..."
    
    if [ ! -f .env.production ]; then
        log_error ".env.production 文件不存在"
        log_info "请复制 .env.production.example 并配置："
        log_info "  cp .env.production.example .env.production"
        log_info "  nano .env.production"
        exit 1
    fi
    
    # 检查是否还有未配置的 CHANGE_ME 值
    if grep -q "CHANGE_ME" .env.production; then
        log_error ".env.production 中仍有未配置的 CHANGE_ME 值"
        log_info "请编辑 .env.production 并替换所有 CHANGE_ME 值"
        exit 1
    fi
    
    log_info "环境配置文件检查通过"
}

# 备份数据
backup_data() {
    log_info "备份现有数据..."
    
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # 备份数据库
    if docker-compose -f docker-compose.prod.yml ps | grep -q literature-db; then
        log_info "备份数据库..."
        docker-compose -f docker-compose.prod.yml exec -T db \
            pg_dump -U prod_user literature_downloads > "$BACKUP_DIR/database.sql"
        log_info "数据库备份完成: $BACKUP_DIR/database.sql"
    fi
    
    log_info "备份完成"
}

# 构建镜像
build_images() {
    log_info "构建 Docker 镜像..."
    docker-compose -f docker-compose.prod.yml build --no-cache
    log_info "镜像构建完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."
    docker-compose -f docker-compose.prod.yml up -d
    log_info "服务启动完成"
}

# 等待服务就绪
wait_for_services() {
    log_info "等待服务就绪..."
    
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f http://localhost:8000/health &> /dev/null; then
            log_info "服务已就绪"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_info "等待中... ($attempt/$max_attempts)"
        sleep 2
    done
    
    log_error "服务启动超时"
    return 1
}

# 运行数据库迁移
run_migrations() {
    log_info "运行数据库迁移..."
    docker-compose -f docker-compose.prod.yml exec -T app alembic upgrade head || {
        log_warn "数据库迁移失败或未配置"
    }
}

# 初始化存储
init_storage() {
    log_info "初始化对象存储..."
    docker-compose -f docker-compose.prod.yml exec -T app python -c "
from app.services.storage import storage_service
storage_service.ensure_bucket()
print('Storage initialized successfully')
" || {
        log_warn "存储初始化失败"
    }
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    # 检查 API
    if curl -f http://localhost:8000/health &> /dev/null; then
        log_info "✓ API 服务正常"
    else
        log_error "✗ API 服务异常"
        return 1
    fi
    
    # 检查 Celery
    if docker-compose -f docker-compose.prod.yml exec -T celery \
        celery -A app.celery_app inspect ping &> /dev/null; then
        log_info "✓ Celery Worker 正常"
    else
        log_error "✗ Celery Worker 异常"
        return 1
    fi
    
    log_info "健康检查通过"
}

# 显示服务状态
show_status() {
    log_info "服务状态："
    docker-compose -f docker-compose.prod.yml ps
    
    log_info ""
    log_info "服务访问地址："
    log_info "  API: http://localhost:8000"
    log_info "  API 文档: http://localhost:8000/docs"
    log_info "  MinIO 控制台: http://localhost:9001"
    log_info ""
    log_info "查看日志："
    log_info "  docker-compose -f docker-compose.prod.yml logs -f app"
    log_info "  docker-compose -f docker-compose.prod.yml logs -f celery"
}

# 主函数
main() {
    log_info "开始部署文献下载服务..."
    
    # 检查环境
    check_requirements
    check_env_file
    
    # 询问是否备份
    read -p "是否备份现有数据？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        backup_data
    fi
    
    # 构建和启动
    build_images
    start_services
    
    # 等待服务就绪
    if ! wait_for_services; then
        log_error "部署失败：服务未能正常启动"
        log_info "查看日志："
        log_info "  docker-compose -f docker-compose.prod.yml logs"
        exit 1
    fi
    
    # 初始化
    run_migrations
    init_storage
    
    # 健康检查
    if ! health_check; then
        log_error "部署失败：健康检查未通过"
        exit 1
    fi
    
    # 显示状态
    show_status
    
    log_info "部署完成！"
}

# 执行主函数
main

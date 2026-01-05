#!/bin/bash

# ============================================
# 服务器端部署脚本
# ============================================
# 功能：
# 1. 加载 Docker 镜像
# 2. 配置环境变量
# 3. 启动服务
# 4. 健康检查
# ============================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
IMAGES_DIR="${PROJECT_DIR}/images"
CONFIG_DIR="${SCRIPT_DIR}"
COMPOSE_FILE="${CONFIG_DIR}/docker-compose.yml"
ENV_FILE="${CONFIG_DIR}/.env.prod"

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

# 检查 Docker
check_docker() {
    log_info "检查 Docker..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker 未运行，请先启动 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    log_info "Docker 检查通过"
}

# 检查必要的文件
check_files() {
    log_info "检查必要文件..."
    
    if [ ! -d "${IMAGES_DIR}" ]; then
        log_error "镜像目录不存在: ${IMAGES_DIR}"
        exit 1
    fi
    
    if [ ! -f "${COMPOSE_FILE}" ]; then
        log_error "docker-compose.yml 不存在: ${COMPOSE_FILE}"
        exit 1
    fi
    
    if [ ! -f "${ENV_FILE}" ]; then
        log_warn "环境变量文件不存在: ${ENV_FILE}"
        log_warn "将使用 env.prod.example（如果存在）"
        if [ -f "${CONFIG_DIR}/env.prod.example" ]; then
            cp "${CONFIG_DIR}/env.prod.example" "${ENV_FILE}"
            log_warn "已复制 env.prod.example 为 .env.prod"
            log_warn "请编辑 .env.prod 文件后重新运行部署脚本"
            exit 1
        else
            log_error "未找到环境变量配置文件"
            exit 1
        fi
    fi
    
    log_info "文件检查通过"
}

# 加载 Docker 镜像
load_images() {
    log_info "加载 Docker 镜像..."
    
    local image_count=0
    local loaded_count=0
    
    # 查找所有镜像文件
    for image_file in "${IMAGES_DIR}"/*.tar.gz; do
        if [ -f "${image_file}" ]; then
            image_count=$((image_count + 1))
            local filename=$(basename "${image_file}")
            log_info "加载镜像: ${filename}"
            
            # 解压并加载
            gunzip -c "${image_file}" | docker load
            
            if [ $? -eq 0 ]; then
                loaded_count=$((loaded_count + 1))
                log_info "镜像加载成功: ${filename}"
            else
                log_error "镜像加载失败: ${filename}"
                exit 1
            fi
        fi
    done
    
    if [ ${image_count} -eq 0 ]; then
        log_error "未找到镜像文件"
        exit 1
    fi
    
    log_info "镜像加载完成: ${loaded_count}/${image_count}"
}

# 备份现有服务（如果存在）
backup_existing() {
    if docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps -q 2>/dev/null | grep -q .; then
        log_info "检测到现有服务，创建备份..."
        
        BACKUP_DIR="${PROJECT_DIR}/backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "${BACKUP_DIR}"
        
        # 备份环境变量
        if [ -f "${ENV_FILE}" ]; then
            cp "${ENV_FILE}" "${BACKUP_DIR}/.env.prod.backup"
        fi
        
        # 备份 docker-compose.yml
        cp "${COMPOSE_FILE}" "${BACKUP_DIR}/docker-compose.yml.backup"
        
        log_info "备份完成: ${BACKUP_DIR}"
    fi
}

# 停止现有服务
stop_existing_services() {
    log_info "停止现有服务..."
    
    cd "${PROJECT_DIR}"
    
    if docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps -q 2>/dev/null | grep -q .; then
        docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
        log_info "现有服务已停止"
    else
        log_info "未发现运行中的服务"
    fi
}

# 启动基础设施服务
start_infrastructure() {
    log_info "启动基础设施服务..."
    
    cd "${PROJECT_DIR}"
    
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d \
        rabbitmq minio redis db discovery_db parser_db indexing_db
    
    log_info "等待基础设施服务就绪..."
    sleep 30
    
    # 验证基础设施
    log_info "验证基础设施服务..."
    
    # 检查 RabbitMQ
    if docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T rabbitmq rabbitmqctl status > /dev/null 2>&1; then
        log_info "✓ RabbitMQ 就绪"
    else
        log_warn "✗ RabbitMQ 未就绪，继续等待..."
    fi
    
    # 检查 MinIO
    if curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; then
        log_info "✓ MinIO 就绪"
    else
        log_warn "✗ MinIO 未就绪"
    fi
    
    # 检查 Redis
    if docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T redis redis-cli -a WFWwfw123... ping > /dev/null 2>&1; then
        log_info "✓ Redis 就绪"
    else
        log_warn "✗ Redis 未就绪"
    fi
    
    log_info "基础设施服务启动完成"
}

# 执行数据库迁移
run_migrations() {
    log_info "执行数据库迁移..."
    
    cd "${PROJECT_DIR}"
    
    # Discovery Service 迁移
    if docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" run --rm discovery_migrations 2>/dev/null; then
        log_info "✓ Discovery Service 迁移完成"
    else
        log_warn "Discovery Service 迁移失败或已是最新版本"
    fi
    
    # Parser Service 迁移
    if docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" run --rm parser_migrations 2>/dev/null; then
        log_info "✓ Parser Service 迁移完成"
    else
        log_warn "Parser Service 迁移失败或已是最新版本"
    fi
    
    # Indexing Service 迁移
    if docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" run --rm indexing_migrations 2>/dev/null; then
        log_info "✓ Indexing Service 迁移完成"
    else
        log_warn "Indexing Service 迁移失败或已是最新版本"
    fi
}

# 启动所有服务
start_all_services() {
    log_info "启动所有服务..."
    
    cd "${PROJECT_DIR}"
    
    # 使用 --no-build 参数，因为镜像已经加载
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --no-build
    
    log_info "等待服务启动..."
    sleep 20
    
    log_info "所有服务启动完成"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    local max_attempts=30
    local attempt=0
    local all_healthy=false
    
    while [ $attempt -lt $max_attempts ]; do
        attempt=$((attempt + 1))
        log_info "健康检查尝试 ${attempt}/${max_attempts}..."
        
        # 检查 Application Service
        if curl -f http://localhost:8005/health > /dev/null 2>&1; then
            log_info "✓ Application Service 健康"
        else
            log_warn "✗ Application Service 未就绪"
            sleep 5
            continue
        fi
        
        # 检查 Frontend
        if curl -f http://localhost:3000 > /dev/null 2>&1; then
            log_info "✓ Frontend 健康"
        else
            log_warn "✗ Frontend 未就绪"
            sleep 5
            continue
        fi
        
        all_healthy=true
        break
    done
    
    if [ "$all_healthy" = true ]; then
        log_info "所有服务健康检查通过"
        return 0
    else
        log_error "部分服务健康检查失败"
        log_info "查看服务状态: docker-compose ps"
        log_info "查看服务日志: docker-compose logs -f"
        return 1
    fi
}

# 显示服务状态
show_status() {
    log_info "============================================"
    log_info "部署完成！"
    log_info "============================================"
    log_info "服务状态:"
    cd "${PROJECT_DIR}"
    docker-compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps
    log_info ""
    log_info "访问地址:"
    log_info "  - 前端: http://localhost:3000"
    log_info "  - 应用服务: http://localhost:8005"
    log_info "  - API 文档: http://localhost:8005/docs"
    log_info ""
    log_info "查看日志:"
    log_info "  docker-compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} logs -f"
    log_info ""
    log_info "停止服务:"
    log_info "  docker-compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} down"
    log_info "============================================"
}

# 主函数
main() {
    log_info "============================================"
    log_info "服务器端部署脚本"
    log_info "============================================"
    
    check_docker
    check_files
    backup_existing
    stop_existing_services
    load_images
    start_infrastructure
    run_migrations
    start_all_services
    
    # 等待服务就绪
    sleep 10
    
    if health_check; then
        show_status
    else
        log_error "部署完成，但部分服务未通过健康检查"
        log_info "请检查服务日志排查问题"
        exit 1
    fi
}

# 执行主函数
main "$@"


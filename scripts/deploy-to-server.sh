#!/bin/bash

# ============================================
# 部署包上传到服务器脚本
# ============================================
# 功能：
# 1. 上传部署包到服务器
# 2. 上传配置文件
# 3. 在服务器上执行部署脚本
# ============================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置（从环境变量或参数获取）
SERVER_IP=${SERVER_IP:-"8.134.183.68"}
SERVER_USER=${SERVER_USER:-"root"}
REMOTE_PATH=${REMOTE_PATH:-"~/myapp"}
DEPLOYMENT_PACKAGE=${1:-""}

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
    log_info "检查必要工具..."
    
    if ! command -v scp &> /dev/null; then
        log_error "未找到 scp 命令，请安装 OpenSSH"
        exit 1
    fi
    
    if ! command -v ssh &> /dev/null; then
        log_error "未找到 ssh 命令，请安装 OpenSSH"
        exit 1
    fi
    
    log_info "工具检查通过"
}

# 查找最新的部署包
find_latest_package() {
    if [ -z "${DEPLOYMENT_PACKAGE}" ]; then
        log_info "查找最新的部署包..."
        DEPLOYMENT_PACKAGE=$(ls -t deployment-package-*.tar.gz 2>/dev/null | head -1)
        
        if [ -z "${DEPLOYMENT_PACKAGE}" ]; then
            log_error "未找到部署包，请先运行 scripts/build-and-package.sh"
            exit 1
        fi
        
        log_info "找到部署包: ${DEPLOYMENT_PACKAGE}"
    fi
    
    if [ ! -f "${DEPLOYMENT_PACKAGE}" ]; then
        log_error "部署包不存在: ${DEPLOYMENT_PACKAGE}"
        exit 1
    fi
}

# 测试服务器连接
test_connection() {
    log_info "测试服务器连接: ${SERVER_USER}@${SERVER_IP}"
    
    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
        "${SERVER_USER}@${SERVER_IP}" "echo '连接成功'" > /dev/null 2>&1; then
        log_info "服务器连接成功"
    else
        log_error "无法连接到服务器，请检查："
        log_error "1. 服务器 IP 是否正确: ${SERVER_IP}"
        log_error "2. SSH 密钥是否配置"
        log_error "3. 服务器是否可访问"
        exit 1
    fi
}

# 在服务器上创建目录
create_remote_dirs() {
    log_info "在服务器上创建目录: ${REMOTE_PATH}"
    
    ssh "${SERVER_USER}@${SERVER_IP}" << EOF
        mkdir -p ${REMOTE_PATH}
        mkdir -p ${REMOTE_PATH}/images
        mkdir -p ${REMOTE_PATH}/config
        mkdir -p ${REMOTE_PATH}/backups
EOF
    
    log_info "服务器目录创建完成"
}

# 上传部署包
upload_package() {
    log_info "上传部署包到服务器..."
    
    local package_size=$(du -h "${DEPLOYMENT_PACKAGE}" | cut -f1)
    log_info "文件大小: ${package_size}"
    
    scp "${DEPLOYMENT_PACKAGE}" "${SERVER_USER}@${SERVER_IP}:${REMOTE_PATH}/"
    
    if [ $? -eq 0 ]; then
        log_info "部署包上传成功"
    else
        log_error "部署包上传失败"
        exit 1
    fi
}

# 在服务器上解压部署包
extract_package() {
    log_info "在服务器上解压部署包..."
    
    local package_name=$(basename "${DEPLOYMENT_PACKAGE}")
    
    ssh "${SERVER_USER}@${SERVER_IP}" << EOF
        cd ${REMOTE_PATH}
        tar -xzf ${package_name}
        log_info "部署包解压完成"
EOF
    
    log_info "部署包解压完成"
}

# 上传环境变量文件（如果存在）
upload_env_file() {
    if [ -f ".env.prod" ]; then
        log_info "上传环境变量文件..."
        scp ".env.prod" "${SERVER_USER}@${SERVER_IP}:${REMOTE_PATH}/config/"
        log_info "环境变量文件上传完成"
    else
        log_warn "未找到 .env.prod 文件，将使用 env.prod.example"
        log_warn "请在服务器上手动创建 .env.prod 文件"
    fi
}

# 执行服务器端部署脚本
execute_deployment() {
    log_info "执行服务器端部署脚本..."
    
    ssh "${SERVER_USER}@${SERVER_IP}" << EOF
        cd ${REMOTE_PATH}
        chmod +x config/server-deploy.sh
        
        # 检查是否有 .env.prod，如果没有则提示
        if [ ! -f "config/.env.prod" ]; then
            echo "警告: 未找到 .env.prod 文件"
            echo "请先创建配置文件:"
            echo "  cp config/env.prod.example config/.env.prod"
            echo "  nano config/.env.prod"
            echo ""
            read -p "是否现在创建配置文件? (y/n) " -n 1 -r
            echo
            if [[ \$REPLY =~ ^[Yy]\$ ]]; then
                cp config/env.prod.example config/.env.prod
                echo "请编辑配置文件后继续部署"
                exit 1
            fi
        fi
        
        # 执行部署脚本
        ./config/server-deploy.sh
EOF
    
    if [ $? -eq 0 ]; then
        log_info "服务器端部署完成"
    else
        log_error "服务器端部署失败，请检查日志"
        exit 1
    fi
}

# 显示部署信息
show_deployment_info() {
    log_info "============================================"
    log_info "部署完成！"
    log_info "============================================"
    log_info "服务器: ${SERVER_USER}@${SERVER_IP}"
    log_info "部署路径: ${REMOTE_PATH}"
    log_info ""
    log_info "访问地址:"
    log_info "  - 前端: http://${SERVER_IP}:3000"
    log_info "  - 应用服务: http://${SERVER_IP}:8005"
    log_info "  - API 文档: http://${SERVER_IP}:8005/docs"
    log_info ""
    log_info "查看服务状态:"
    log_info "  ssh ${SERVER_USER}@${SERVER_IP} 'cd ${REMOTE_PATH} && docker-compose ps'"
    log_info ""
    log_info "查看服务日志:"
    log_info "  ssh ${SERVER_USER}@${SERVER_IP} 'cd ${REMOTE_PATH} && docker-compose logs -f'"
    log_info "============================================"
}

# 主函数
main() {
    log_info "============================================"
    log_info "部署包上传到服务器"
    log_info "服务器: ${SERVER_USER}@${SERVER_IP}"
    log_info "============================================"
    
    check_requirements
    find_latest_package
    test_connection
    create_remote_dirs
    upload_package
    extract_package
    upload_env_file
    
    # 询问是否立即部署
    read -p "是否立即在服务器上执行部署? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        execute_deployment
        show_deployment_info
    else
        log_info "部署包已上传，请手动在服务器上执行部署:"
        log_info "  ssh ${SERVER_USER}@${SERVER_IP}"
        log_info "  cd ${REMOTE_PATH}"
        log_info "  ./config/server-deploy.sh"
    fi
}

# 执行主函数
main "$@"


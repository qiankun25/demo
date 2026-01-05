#!/bin/bash

# ============================================
# 生产环境镜像构建与打包脚本
# ============================================
# 功能：
# 1. 构建所有 Docker 镜像（带版本标签）
# 2. 保存镜像为 tar 文件
# 3. 打包配置文件
# 4. 生成部署包
# ============================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
VERSION=${1:-$(date +%Y%m%d_%H%M%S)}
BUILD_DIR="build"
IMAGES_DIR="${BUILD_DIR}/images"
CONFIG_DIR="${BUILD_DIR}/config"
PACKAGE_NAME="deployment-package-${VERSION}.tar.gz"

# 需要构建的服务列表（从 docker-compose.yml 中提取）
SERVICES=(
    "nexus:./nexus/Dockerfile"
    "discovery_service:./tool_services/discovery_service/Dockerfile"
    "download_service:./tool_services/download_service/Dockerfile"
    "parser_service:./tool_services/parser_service/Dockerfile"
    "indexing_service:./tool_services/indexing_service/Dockerfile"
    "overview_service:./tool_services/overview_service/Dockerfile"
    "retrieval_service:./tool_services/retrieval_service/Dockerfile"
    "translator_service:./tool_services/translator_service/Dockerfile"
    "application_service:./application_service/Dockerfile"
    "frontend:./frontend/Dockerfile"
)

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

# 检查 Docker 是否运行
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker 未运行，请先启动 Docker"
        exit 1
    fi
    log_info "Docker 检查通过"
}

# 创建构建目录
create_build_dirs() {
    log_info "创建构建目录..."
    mkdir -p "${IMAGES_DIR}"
    mkdir -p "${CONFIG_DIR}"
    log_info "构建目录创建完成"
}

# 构建单个服务镜像
build_service() {
    local service_name=$1
    local dockerfile_path=$2
    local image_tag="${service_name}:${VERSION}"
    local image_latest="${service_name}:latest"
    
    log_info "构建镜像: ${service_name} (版本: ${VERSION})"
    
    # 根据服务类型选择构建方式
    case ${service_name} in
        "frontend")
            # Frontend 需要构建参数
            if [ -z "${VITE_API_BASE_URL}" ] || [ -z "${VITE_MINIO_UPLOAD_URL}" ]; then
                log_warn "Frontend 构建参数未设置，使用默认值"
                export VITE_API_BASE_URL=${VITE_API_BASE_URL:-"http://localhost:8005/api/v1"}
                export VITE_MINIO_UPLOAD_URL=${VITE_MINIO_UPLOAD_URL:-"http://localhost:8001/upload"}
            fi
            docker build \
                --build-arg VITE_API_BASE_URL="${VITE_API_BASE_URL}" \
                --build-arg VITE_MINIO_UPLOAD_URL="${VITE_MINIO_UPLOAD_URL}" \
                -f "${dockerfile_path}" \
                -t "${image_tag}" \
                -t "${image_latest}" \
                .
            ;;
        *)
            # 其他服务直接构建
            docker build \
                -f "${dockerfile_path}" \
                -t "${image_tag}" \
                -t "${image_latest}" \
                .
            ;;
    esac
    
    if [ $? -eq 0 ]; then
        log_info "镜像构建成功: ${image_tag}"
    else
        log_error "镜像构建失败: ${service_name}"
        exit 1
    fi
}

# 保存镜像为 tar 文件
save_image() {
    local service_name=$1
    local image_tag="${service_name}:${VERSION}"
    local tar_file="${IMAGES_DIR}/${service_name}_${VERSION}.tar"
    
    log_info "保存镜像: ${service_name} -> ${tar_file}"
    
    docker save "${image_tag}" -o "${tar_file}"
    
    if [ $? -eq 0 ]; then
        # 压缩 tar 文件
        log_info "压缩镜像文件: ${tar_file}"
        gzip -f "${tar_file}"
        log_info "镜像保存成功: ${tar_file}.gz"
        
        # 显示文件大小
        local size=$(du -h "${tar_file}.gz" | cut -f1)
        log_info "文件大小: ${size}"
    else
        log_error "镜像保存失败: ${service_name}"
        exit 1
    fi
}

# 构建所有服务
build_all_services() {
    log_info "开始构建所有服务镜像..."
    
    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r service_name dockerfile_path <<< "${service_info}"
        build_service "${service_name}" "${dockerfile_path}"
        save_image "${service_name}"
    done
    
    log_info "所有服务镜像构建完成"
}

# 复制配置文件
copy_config_files() {
    log_info "复制配置文件..."
    
    # 复制 docker-compose.yml
    if [ -f "docker-compose.yml" ]; then
        cp docker-compose.yml "${CONFIG_DIR}/"
        log_info "已复制: docker-compose.yml"
    else
        log_error "未找到 docker-compose.yml"
        exit 1
    fi
    
    # 复制环境变量示例文件
    if [ -f "env.prod.example" ]; then
        cp env.prod.example "${CONFIG_DIR}/"
        log_info "已复制: env.prod.example"
    fi
    
    # 复制部署脚本
    if [ -f "scripts/server-deploy.sh" ]; then
        cp scripts/server-deploy.sh "${CONFIG_DIR}/"
        chmod +x "${CONFIG_DIR}/server-deploy.sh"
        log_info "已复制: server-deploy.sh"
    fi
    
    log_info "配置文件复制完成"
}

# 创建版本信息文件
create_version_info() {
    log_info "创建版本信息文件..."
    
    cat > "${BUILD_DIR}/VERSION" << EOF
版本: ${VERSION}
构建时间: $(date '+%Y-%m-%d %H:%M:%S')
构建用户: $(whoami)
构建主机: $(hostname)
Git 提交: $(git rev-parse HEAD 2>/dev/null || echo "N/A")
Git 分支: $(git branch --show-current 2>/dev/null || echo "N/A")
EOF
    
    log_info "版本信息文件创建完成"
}

# 创建服务清单
create_manifest() {
    log_info "创建服务清单..."
    
    cat > "${BUILD_DIR}/MANIFEST" << EOF
# 部署包清单
版本: ${VERSION}
构建时间: $(date '+%Y-%m-%d %H:%M:%S')

## 镜像列表
EOF
    
    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r service_name dockerfile_path <<< "${service_info}"
        local tar_file="${service_name}_${VERSION}.tar.gz"
        if [ -f "${IMAGES_DIR}/${tar_file}" ]; then
            local size=$(du -h "${IMAGES_DIR}/${tar_file}" | cut -f1)
            echo "- ${service_name}: ${tar_file} (${size})" >> "${BUILD_DIR}/MANIFEST"
        fi
    done
    
    echo "" >> "${BUILD_DIR}/MANIFEST"
    echo "## 配置文件" >> "${BUILD_DIR}/MANIFEST"
    echo "- docker-compose.yml" >> "${BUILD_DIR}/MANIFEST"
    echo "- env.prod.example" >> "${BUILD_DIR}/MANIFEST"
    echo "- server-deploy.sh" >> "${BUILD_DIR}/MANIFEST"
    
    log_info "服务清单创建完成"
}

# 打包部署包
package_deployment() {
    log_info "打包部署包..."
    
    cd "${BUILD_DIR}"
    tar -czf "../${PACKAGE_NAME}" \
        images/ \
        config/ \
        VERSION \
        MANIFEST
    
    cd ..
    
    if [ $? -eq 0 ]; then
        local size=$(du -h "${PACKAGE_NAME}" | cut -f1)
        log_info "部署包创建成功: ${PACKAGE_NAME} (${size})"
    else
        log_error "部署包创建失败"
        exit 1
    fi
}

# 清理临时文件（可选）
cleanup() {
    if [ "${CLEANUP_TEMP:-false}" = "true" ]; then
        log_info "清理临时文件..."
        rm -rf "${BUILD_DIR}"
        log_info "临时文件清理完成"
    else
        log_info "保留构建目录: ${BUILD_DIR}"
        log_info "如需清理，请运行: rm -rf ${BUILD_DIR}"
    fi
}

# 主函数
main() {
    log_info "============================================"
    log_info "生产环境镜像构建与打包"
    log_info "版本: ${VERSION}"
    log_info "============================================"
    
    check_docker
    create_build_dirs
    build_all_services
    copy_config_files
    create_version_info
    create_manifest
    package_deployment
    cleanup
    
    log_info "============================================"
    log_info "构建完成！"
    log_info "部署包: ${PACKAGE_NAME}"
    log_info "下一步: 运行 scripts/deploy-to-server.sh 上传到服务器"
    log_info "============================================"
}

# 执行主函数
main "$@"


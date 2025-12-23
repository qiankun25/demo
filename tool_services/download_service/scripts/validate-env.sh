#!/bin/bash

# ============================================
# 环境变量验证脚本
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ENV_FILE="${1:-.env.production}"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}错误: 文件 $ENV_FILE 不存在${NC}"
    exit 1
fi

echo "验证环境配置文件: $ENV_FILE"
echo ""

# 必需的环境变量
REQUIRED_VARS=(
    "DATABASE_URL"
    "REDIS_URL"
    "MINIO_ENDPOINT"
    "MINIO_ACCESS_KEY"
    "MINIO_SECRET_KEY"
)

# 检查必需变量
MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" "$ENV_FILE"; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${RED}错误: 缺少必需的环境变量:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

# 检查是否有未配置的 CHANGE_ME 值
if grep -q "CHANGE_ME" "$ENV_FILE"; then
    echo -e "${YELLOW}警告: 发现未配置的 CHANGE_ME 值:${NC}"
    grep "CHANGE_ME" "$ENV_FILE" | while read -r line; do
        echo "  $line"
    done
    echo ""
    echo -e "${RED}请修改所有 CHANGE_ME 值后再部署${NC}"
    exit 1
fi

# 检查密码强度
check_password_strength() {
    local var_name=$1
    local password=$(grep "^${var_name}=" "$ENV_FILE" | cut -d'=' -f2)
    
    if [ ${#password} -lt 12 ]; then
        echo -e "${YELLOW}警告: $var_name 密码长度少于 12 个字符${NC}"
    fi
}

# 检查关键密码
check_password_strength "POSTGRES_PASSWORD"
check_password_strength "REDIS_PASSWORD"
check_password_strength "MINIO_SECRET_KEY"

# 检查 API Keys
if grep -q "^ALLOWED_API_KEYS=" "$ENV_FILE"; then
    API_KEYS=$(grep "^ALLOWED_API_KEYS=" "$ENV_FILE" | cut -d'=' -f2)
    if [ -z "$API_KEYS" ]; then
        echo -e "${YELLOW}警告: ALLOWED_API_KEYS 为空，API 将不受保护${NC}"
    fi
fi

# 检查 CORS 配置
if grep -q "^CORS_ORIGINS=\*" "$ENV_FILE"; then
    echo -e "${YELLOW}警告: CORS_ORIGINS 设置为 *，允许所有来源访问${NC}"
fi

echo ""
echo -e "${GREEN}✓ 环境配置验证通过${NC}"
echo ""
echo "建议："
echo "  1. 确保所有密码足够强（至少 12 个字符）"
echo "  2. 配置 ALLOWED_API_KEYS 以保护 API"
echo "  3. 限制 CORS_ORIGINS 到特定域名"
echo "  4. 在生产环境启用 HTTPS (MINIO_SECURE=true)"

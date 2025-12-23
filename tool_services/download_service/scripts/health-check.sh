#!/bin/bash

# ============================================
# 健康检查脚本
# ============================================

set -e

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

API_URL="${API_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-}"

echo "检查文献下载服务健康状态..."
echo "API URL: $API_URL"
echo ""

# 检查 API 健康端点
echo -n "检查 API 服务... "
if curl -f -s "$API_URL/health" > /dev/null; then
    echo -e "${GREEN}✓ 正常${NC}"
else
    echo -e "${RED}✗ 异常${NC}"
    exit 1
fi

# 检查数据库连接
echo -n "检查数据库连接... "
DB_STATUS=$(curl -s "$API_URL/health" | grep -o '"database":"[^"]*"' | cut -d'"' -f4)
if [ "$DB_STATUS" = "ok" ]; then
    echo -e "${GREEN}✓ 正常${NC}"
else
    echo -e "${RED}✗ 异常${NC}"
    exit 1
fi

# 检查 Redis 连接
echo -n "检查 Redis 连接... "
REDIS_STATUS=$(curl -s "$API_URL/health" | grep -o '"redis":"[^"]*"' | cut -d'"' -f4)
if [ "$REDIS_STATUS" = "ok" ]; then
    echo -e "${GREEN}✓ 正常${NC}"
else
    echo -e "${RED}✗ 异常${NC}"
    exit 1
fi

# 检查对象存储
echo -n "检查对象存储... "
STORAGE_STATUS=$(curl -s "$API_URL/health" | grep -o '"storage":"[^"]*"' | cut -d'"' -f4)
if [ "$STORAGE_STATUS" = "ok" ]; then
    echo -e "${GREEN}✓ 正常${NC}"
else
    echo -e "${RED}✗ 异常${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}所有检查通过！${NC}"
exit 0

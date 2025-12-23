#!/bin/bash

# 快速测试 Dify 到下载服务的连接
# 用于验证网络配置是否正确

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "Dify 连接测试"
echo "========================================="
echo ""

# 测试 1: 从宿主机访问服务
echo -e "${YELLOW}测试 1: 从宿主机访问服务${NC}"
echo "URL: http://localhost:8000/health"
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✓ 服务在宿主机上正常运行${NC}"
else
    echo -e "${RED}✗ 服务未运行或无法访问${NC}"
    exit 1
fi
echo ""

# 测试 2: 从 Dify 容器访问服务（使用 host.docker.internal）
echo -e "${YELLOW}测试 2: 从 Dify 容器访问服务（host.docker.internal）${NC}"
echo "URL: http://host.docker.internal:8000/health"
if docker exec docker-api-1 curl -s http://host.docker.internal:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Dify 可以通过 host.docker.internal 访问服务${NC}"
    RESPONSE=$(docker exec docker-api-1 curl -s http://host.docker.internal:8000/health)
    echo "响应: $RESPONSE"
else
    echo -e "${RED}✗ Dify 无法通过 host.docker.internal 访问服务${NC}"
    echo ""
    echo "可能的原因："
    echo "1. Docker Desktop 未启用 host.docker.internal"
    echo "2. 防火墙阻止了连接"
    echo "3. Dify 容器网络配置问题"
    exit 1
fi
echo ""

# 测试 3: 测试创建下载任务
echo -e "${YELLOW}测试 3: 从 Dify 容器创建下载任务${NC}"
RESPONSE=$(docker exec docker-api-1 curl -s -X POST http://host.docker.internal:8000/download \
    -H "Content-Type: application/json" \
    -d '{"url": "https://arxiv.org/pdf/2301.00001.pdf"}')

if echo "$RESPONSE" | grep -q "task_id"; then
    echo -e "${GREEN}✓ 成功创建下载任务${NC}"
    echo "响应: $RESPONSE"
else
    echo -e "${RED}✗ 创建任务失败${NC}"
    echo "响应: $RESPONSE"
    exit 1
fi
echo ""

# 总结
echo "========================================="
echo -e "${GREEN}所有测试通过！${NC}"
echo "========================================="
echo ""
echo "✅ 在 Dify 中使用以下服务器地址："
echo "   http://host.docker.internal:8000"
echo ""
echo "📝 下一步："
echo "1. 在 Dify 中导入 docs/openapi.json"
echo "2. 选择服务器: http://host.docker.internal:8000"
echo "3. 测试工具调用"

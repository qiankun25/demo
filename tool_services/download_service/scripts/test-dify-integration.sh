#!/bin/bash

# Dify 集成测试脚本
# 用于验证 Literature Download Service 与 Dify 的集成配置

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
SERVICE_URL="${SERVICE_URL:-http://literature-download-service:8000}"
API_KEY="${API_KEY:-your-api-key-here}"
TEST_URL="https://arxiv.org/pdf/2301.00001.pdf"

echo "========================================="
echo "Dify 集成测试"
echo "========================================="
echo ""

# 测试 1: 健康检查
echo -e "${YELLOW}测试 1: 健康检查${NC}"
echo "URL: $SERVICE_URL/health"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$SERVICE_URL/health")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 健康检查通过${NC}"
    echo "响应: $BODY"
else
    echo -e "${RED}✗ 健康检查失败 (HTTP $HTTP_CODE)${NC}"
    echo "响应: $BODY"
    exit 1
fi
echo ""

# 测试 2: 创建下载任务（无认证）
echo -e "${YELLOW}测试 2: 创建下载任务（无认证）${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$SERVICE_URL/download" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$TEST_URL\"}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
    echo -e "${GREEN}✓ 正确拒绝未认证请求${NC}"
elif [ "$HTTP_CODE" = "201" ]; then
    echo -e "${YELLOW}⚠ 警告: 服务未启用认证，任务已创建 (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}✗ 意外响应 (HTTP $HTTP_CODE)${NC}"
fi
echo ""

# 测试 3: 创建下载任务（有认证）
echo -e "${YELLOW}测试 3: 创建下载任务${NC}"
echo "URL: $SERVICE_URL/download"
echo "API Key: ${API_KEY:0:10}..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$SERVICE_URL/download" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{\"url\": \"$TEST_URL\"}")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "201" ]; then
    echo -e "${GREEN}✓ 任务创建成功${NC}"
    echo "响应: $BODY"
    TASK_ID=$(echo "$BODY" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
    echo "任务 ID: $TASK_ID"
else
    echo -e "${RED}✗ 任务创建失败 (HTTP $HTTP_CODE)${NC}"
    echo "响应: $BODY"
    exit 1
fi
echo ""

# 测试 4: 查询任务状态
if [ -n "$TASK_ID" ]; then
    echo -e "${YELLOW}测试 4: 查询任务状态${NC}"
    echo "等待 3 秒..."
    sleep 3
    
    for i in {1..5}; do
        echo "尝试 $i/5..."
        RESPONSE=$(curl -s -w "\n%{http_code}" "$SERVICE_URL/download/$TASK_ID" \
            -H "X-API-Key: $API_KEY")
        HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
        BODY=$(echo "$RESPONSE" | head -n-1)
        
        if [ "$HTTP_CODE" = "200" ]; then
            echo -e "${GREEN}✓ 状态查询成功${NC}"
            echo "响应: $BODY"
            
            STATUS=$(echo "$BODY" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
            echo "当前状态: $STATUS"
            
            if [ "$STATUS" = "success" ]; then
                FILE_URL=$(echo "$BODY" | grep -o '"file_url":"[^"]*"' | cut -d'"' -f4)
                echo -e "${GREEN}✓ 下载完成！${NC}"
                echo "文件 URL: $FILE_URL"
                break
            elif [ "$STATUS" = "failed" ]; then
                ERROR=$(echo "$BODY" | grep -o '"error_message":"[^"]*"' | cut -d'"' -f4)
                echo -e "${RED}✗ 下载失败: $ERROR${NC}"
                break
            else
                echo "任务仍在处理中，等待 5 秒..."
                sleep 5
            fi
        else
            echo -e "${RED}✗ 状态查询失败 (HTTP $HTTP_CODE)${NC}"
            echo "响应: $BODY"
            break
        fi
    done
fi
echo ""

# 测试 5: OpenAPI 规范验证
echo -e "${YELLOW}测试 5: OpenAPI 规范验证${NC}"
if [ -f "docs/openapi.json" ]; then
    echo -e "${GREEN}✓ OpenAPI 规范文件存在${NC}"
    echo "文件路径: docs/openapi.json"
    
    # 验证 JSON 格式
    if command -v jq &> /dev/null; then
        if jq empty docs/openapi.json 2>/dev/null; then
            echo -e "${GREEN}✓ JSON 格式有效${NC}"
        else
            echo -e "${RED}✗ JSON 格式无效${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ 未安装 jq，跳过 JSON 验证${NC}"
    fi
else
    echo -e "${RED}✗ OpenAPI 规范文件不存在${NC}"
fi
echo ""

# 总结
echo "========================================="
echo -e "${GREEN}测试完成！${NC}"
echo "========================================="
echo ""
echo "下一步："
echo "1. 将 docs/openapi.json 导入到 Dify"
echo "2. 在 Dify 中配置 API Key: $API_KEY"
echo "3. 创建工作流并测试工具调用"
echo ""
echo "详细文档: docs/DIFY_INTEGRATION.md"

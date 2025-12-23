# 快速测试 Dify 到下载服务的连接
# 用于验证网络配置是否正确

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Dify 连接测试" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# 测试 1: 从宿主机访问服务
Write-Host "测试 1: 从宿主机访问服务" -ForegroundColor Yellow
Write-Host "URL: http://localhost:8000/health"
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction Stop
    Write-Host "✓ 服务在宿主机上正常运行" -ForegroundColor Green
    Write-Host "响应: $($response.Content)"
} catch {
    Write-Host "✗ 服务未运行或无法访问" -ForegroundColor Red
    Write-Host "错误: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 测试 2: 从 Dify 容器访问服务（使用 host.docker.internal）
Write-Host "测试 2: 从 Dify 容器访问服务（host.docker.internal）" -ForegroundColor Yellow
Write-Host "URL: http://host.docker.internal:8000/health"
try {
    $response = docker exec docker-api-1 curl -s http://host.docker.internal:8000/health 2>&1
    if ($LASTEXITCODE -eq 0 -and $response -match "status") {
        Write-Host "✓ Dify 可以通过 host.docker.internal 访问服务" -ForegroundColor Green
        Write-Host "响应: $response"
    } else {
        throw "无法访问服务"
    }
} catch {
    Write-Host "✗ Dify 无法通过 host.docker.internal 访问服务" -ForegroundColor Red
    Write-Host ""
    Write-Host "可能的原因："
    Write-Host "1. Docker Desktop 未启用 host.docker.internal"
    Write-Host "2. 防火墙阻止了连接"
    Write-Host "3. Dify 容器网络配置问题"
    exit 1
}
Write-Host ""

# 测试 3: 测试创建下载任务
Write-Host "测试 3: 从 Dify 容器创建下载任务" -ForegroundColor Yellow
try {
    $response = docker exec docker-api-1 curl -s -X POST http://host.docker.internal:8000/download -H "Content-Type: application/json" -d '{\"url\": \"https://arxiv.org/pdf/2301.00001.pdf\"}' 2>&1
    
    if ($response -match "task_id") {
        Write-Host "✓ 成功创建下载任务" -ForegroundColor Green
        Write-Host "响应: $response"
    } else {
        throw "创建任务失败: $response"
    }
} catch {
    Write-Host "✗ 创建任务失败" -ForegroundColor Red
    Write-Host "响应: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 总结
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "所有测试通过！" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "✅ 在 Dify 中使用以下服务器地址：" -ForegroundColor Green
Write-Host "   http://host.docker.internal:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 下一步："
Write-Host "1. 在 Dify 中导入 docs/openapi.json"
Write-Host "2. 选择服务器: http://host.docker.internal:8000"
Write-Host "3. 测试工具调用"

@echo off
SETLOCAL EnableDelayedExpansion

:: --- 配置信息 (请根据实际情况修改) ---
set SERVER_IP=8.134.183.68
set SERVER_USER=root
set REMOTE_PATH=~/myapp
set IMAGE_NAME=nexus:prod
set TAR_NAME=nexus.tar

echo ========================================
echo   Nexus 生产环境镜像自动化更新脚本
echo ========================================

:: 1. 构建镜像 (自动覆盖旧标签)
echo [1/4] 正在本地构建镜像: %IMAGE_NAME%...
docker build -t %IMAGE_NAME% ./nexus
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] 镜像构建失败。
    pause
    exit /b %ERRORLEVEL%
)

:: 2. 导出镜像 (自动覆盖旧 tar 包)
if not exist images mkdir images
echo [2/4] 正在导出镜像到 images/%TAR_NAME%...
docker save -o images/%TAR_NAME% %IMAGE_NAME%
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] 镜像导出失败。
    pause
    exit /b %ERRORLEVEL%
)

:: 3. 上传镜像 (scp 自动覆盖远程文件)
echo [3/4] 正在上传镜像到服务器 (需输入密码)...
scp images/%TAR_NAME% %SERVER_USER%@%SERVER_IP%:%REMOTE_PATH%/images/
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] 文件上传失败。
    pause
    exit /b %ERRORLEVEL%
)

:: 4. 远程部署
echo [4/4] 正在远程执行部署命令 (需再次输入密码)...
ssh %SERVER_USER%@%SERVER_IP% "docker load -i %REMOTE_PATH%/images/%TAR_NAME% && cd %REMOTE_PATH% && docker compose up -d nexus"

if %ERRORLEVEL% EQU 0 (
    echo ========================================
    echo   Nexus 更新成功！
    echo   访问地址: http://%SERVER_IP%:8000/docs
    echo ========================================
) else (
    echo [ERROR] 远程部署失败。
)

pause
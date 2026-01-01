@echo off
SETLOCAL EnableDelayedExpansion

set "SERVICE=nexus"
set "SERVICES="
set "BATCH_MODE=0"
set "COMPOSE_SERVICE="
set "SERVER_IP=8.134.183.68"
set "SERVER_USER=root"
set "REMOTE_PATH=~/myapp"
set "COMPOSE_FILE=docker-compose.prod.yml"
set "COMPOSE_CMD=docker compose"
set "IMAGE_NAME="
set "BUILD_CONTEXT="
set "DOCKERFILE="
set "TAR_NAME="
set "AUTO=0"
set "DRY_RUN=0"
set "SERVICE_FROM_ARG=0"
set "COMPOSE_SERVICE_FROM_ARG=0"
set "IMAGE_FROM_ARG=0"
set "CONTEXT_FROM_ARG=0"
set "DOCKERFILE_FROM_ARG=0"
set "TAR_FROM_ARG=0"

call :parse_args %*

if "%BATCH_MODE%"=="1" (
  call :batch_process
  exit /b 0
)

if not defined COMPOSE_SERVICE set "COMPOSE_SERVICE=%SERVICE%"

call :apply_defaults "%SERVICE%"
if not defined IMAGE_NAME set "IMAGE_NAME=!DEFAULT_IMAGE!"
if not defined BUILD_CONTEXT set "BUILD_CONTEXT=!DEFAULT_CONTEXT!"
if not defined DOCKERFILE set "DOCKERFILE=!DEFAULT_DOCKERFILE!"
if not defined TAR_NAME set "TAR_NAME=!IMAGE_NAME::=_!.tar"

if "%AUTO%"=="0" (
  call :interactive
)

echo ========================================
echo   Docker 镜像构建 + 远程更新脚本
echo ========================================
echo 服务: !SERVICE!
echo Compose 服务: !COMPOSE_SERVICE!
echo 镜像: !IMAGE_NAME!
echo 构建目录: !BUILD_CONTEXT!
echo Dockerfile: !DOCKERFILE!
echo 导出文件: images\!TAR_NAME!
echo 服务器: !SERVER_USER!@!SERVER_IP!
echo 远程路径: !REMOTE_PATH!
echo Compose 文件: !COMPOSE_FILE!
echo DRY_RUN: !DRY_RUN!
echo ========================================

if not exist "!BUILD_CONTEXT!" (
  echo [ERROR] 构建目录不存在: !BUILD_CONTEXT!
  if "%AUTO%"=="0" pause
  exit /b 2
)

set "DOCKERFILE_PATH="
if defined DOCKERFILE (
  if exist "!DOCKERFILE!" (
    set "DOCKERFILE_PATH=!DOCKERFILE!"
  ) else (
    set "DOCKERFILE_PATH=!BUILD_CONTEXT!\!DOCKERFILE!"
  )
)

echo [1/4] 正在本地构建镜像: !IMAGE_NAME!...
if "%DRY_RUN%"=="1" (
  if defined DOCKERFILE_PATH (
    echo docker build -t !IMAGE_NAME! -f "!DOCKERFILE_PATH!" "!BUILD_CONTEXT!"
  ) else (
    echo docker build -t !IMAGE_NAME! "!BUILD_CONTEXT!"
  )
) else (
  if defined DOCKERFILE_PATH (
    docker build -t !IMAGE_NAME! -f "!DOCKERFILE_PATH!" "!BUILD_CONTEXT!"
  ) else (
    docker build -t !IMAGE_NAME! "!BUILD_CONTEXT!"
  )
  if !ERRORLEVEL! NEQ 0 (
      echo [ERROR] 镜像构建失败。
      if "%AUTO%"=="0" pause
      exit /b !ERRORLEVEL!
  )
)

if not exist images mkdir images
echo [2/4] 正在导出镜像到 images\!TAR_NAME!...
if "%DRY_RUN%"=="1" (
  echo docker save -o "images\!TAR_NAME!" "!IMAGE_NAME!"
) else (
  docker save -o "images\!TAR_NAME!" "!IMAGE_NAME!"
  if !ERRORLEVEL! NEQ 0 (
      echo [ERROR] 镜像导出失败。
      if "%AUTO%"=="0" pause
      exit /b !ERRORLEVEL!
  )
)

echo [3/4] 正在上传镜像到服务器 (需输入密码)...
if "%DRY_RUN%"=="1" (
  echo scp "images\!TAR_NAME!" !SERVER_USER!@!SERVER_IP!:!REMOTE_PATH!/images/
) else (
  scp "images\!TAR_NAME!" !SERVER_USER!@!SERVER_IP!:!REMOTE_PATH!/images/
  if !ERRORLEVEL! NEQ 0 (
      echo [ERROR] 文件上传失败。
      if "%AUTO%"=="0" pause
      exit /b !ERRORLEVEL!
  )
)

echo [4/4] 正在远程执行部署命令 (需再次输入密码)...
if "%DRY_RUN%"=="1" (
  echo ssh !SERVER_USER!@!SERVER_IP! "mkdir -p !REMOTE_PATH!/images && docker load -i !REMOTE_PATH!/images/!TAR_NAME! && cd !REMOTE_PATH! && !COMPOSE_CMD! -f !COMPOSE_FILE! up -d !COMPOSE_SERVICE!"
) else (
  ssh !SERVER_USER!@!SERVER_IP! "mkdir -p !REMOTE_PATH!/images && docker load -i !REMOTE_PATH!/images/!TAR_NAME! && cd !REMOTE_PATH! && !COMPOSE_CMD! -f !COMPOSE_FILE! up -d !COMPOSE_SERVICE!"
  if !ERRORLEVEL! EQU 0 (
      echo ========================================
      echo   更新成功: !COMPOSE_SERVICE!
      echo ========================================
  ) else (
      echo [ERROR] 远程部署失败。
  )
)

if "%AUTO%"=="0" pause
exit /b 0

:parse_args
if "%~1"=="" exit /b 0
for /f "tokens=1,2 delims==" %%A in ("%~1") do (
  set "k=%%~A"
  set "v=%%~B"
)
if /i "!k!"=="service" set "SERVICE=!v!"
if /i "!k!"=="service" set "SERVICE_FROM_ARG=1"
if /i "!k!"=="services" set "SERVICES=!v!"
if /i "!k!"=="services" set "BATCH_MODE=1"
if /i "!k!"=="compose_service" set "COMPOSE_SERVICE=!v!"
if /i "!k!"=="compose_service" set "COMPOSE_SERVICE_FROM_ARG=1"
if /i "!k!"=="ip" set "SERVER_IP=!v!"
if /i "!k!"=="user" set "SERVER_USER=!v!"
if /i "!k!"=="remote" set "REMOTE_PATH=!v!"
if /i "!k!"=="compose" set "COMPOSE_FILE=!v!"
if /i "!k!"=="compose_cmd" set "COMPOSE_CMD=!v!"
if /i "!k!"=="image" set "IMAGE_NAME=!v!"
if /i "!k!"=="image" set "IMAGE_FROM_ARG=1"
if /i "!k!"=="context" set "BUILD_CONTEXT=!v!"
if /i "!k!"=="context" set "CONTEXT_FROM_ARG=1"
if /i "!k!"=="dockerfile" set "DOCKERFILE=!v!"
if /i "!k!"=="dockerfile" set "DOCKERFILE_FROM_ARG=1"
if /i "!k!"=="tar" set "TAR_NAME=!v!"
if /i "!k!"=="tar" set "TAR_FROM_ARG=1"
if /i "!k!"=="auto" set "AUTO=!v!"
if /i "!k!"=="dry_run" set "DRY_RUN=!v!"
shift
goto :parse_args

:apply_defaults
set "DEFAULT_IMAGE="
set "DEFAULT_CONTEXT="
set "DEFAULT_DOCKERFILE="

if /i "%~1"=="nexus" (
  set "DEFAULT_IMAGE=nexus:prod"
  set "DEFAULT_CONTEXT=.\nexus"
)
if /i "%~1"=="discovery_service" (
  set "DEFAULT_IMAGE=discovery_service:prod"
  set "DEFAULT_CONTEXT=."
  set "DEFAULT_DOCKERFILE=tool_services\discovery_service\Dockerfile"
)
if /i "%~1"=="download_service_api" (
  set "DEFAULT_IMAGE=download_service:prod"
  set "DEFAULT_CONTEXT=.\tool_services\download_service"
)
if /i "%~1"=="download_service_worker" (
  set "DEFAULT_IMAGE=download_service:prod"
  set "DEFAULT_CONTEXT=.\tool_services\download_service"
)
if /i "%~1"=="download_tool" (
  set "DEFAULT_IMAGE=download_tool:prod"
  set "DEFAULT_CONTEXT=."
  set "DEFAULT_DOCKERFILE=tool_services\download_service\Dockerfile.tool"
)
if /i "%~1"=="indexing_service" (
  set "DEFAULT_IMAGE=indexing_service:prod"
  set "DEFAULT_CONTEXT=."
  set "DEFAULT_DOCKERFILE=tool_services\indexing_service\Dockerfile"
)
if /i "%~1"=="overview_service" (
  set "DEFAULT_IMAGE=overview_service:prod"
  set "DEFAULT_CONTEXT=."
  set "DEFAULT_DOCKERFILE=tool_services\overview_service\Dockerfile"
)
if /i "%~1"=="paper_analyse_tool" (
  set "DEFAULT_IMAGE=paper_analyse_tool:prod"
  set "DEFAULT_CONTEXT=."
  set "DEFAULT_DOCKERFILE=tool_services\paper_analyse\Dockerfile.tool"
)
if /i "%~1"=="retrieval_service" (
  set "DEFAULT_IMAGE=retrieval_service:prod"
  set "DEFAULT_CONTEXT=."
  set "DEFAULT_DOCKERFILE=tool_services\retrieval_service\Dockerfile"
)
if /i "%~1"=="translator_service" (
  set "DEFAULT_IMAGE=translator_service:prod"
  set "DEFAULT_CONTEXT=."
  set "DEFAULT_DOCKERFILE=tool_services\translator_service\Dockerfile"
)

if not defined DEFAULT_IMAGE set "DEFAULT_IMAGE=%~1:prod"
if not defined DEFAULT_CONTEXT set "DEFAULT_CONTEXT=."
exit /b 0

:interactive
set "old_service=!SERVICE!"
set "tmp="
set /p tmp=服务名 (默认 !SERVICE!):
if not "!tmp!"=="" set "SERVICE=!tmp!"
if /i not "!SERVICE!"=="!old_service!" (
  call :apply_defaults "!SERVICE!"
  if "!COMPOSE_SERVICE_FROM_ARG!"=="0" set "COMPOSE_SERVICE=!SERVICE!"
  if "!IMAGE_FROM_ARG!"=="0" set "IMAGE_NAME=!DEFAULT_IMAGE!"
  if "!CONTEXT_FROM_ARG!"=="0" set "BUILD_CONTEXT=!DEFAULT_CONTEXT!"
  if "!DOCKERFILE_FROM_ARG!"=="0" set "DOCKERFILE=!DEFAULT_DOCKERFILE!"
  if "!TAR_FROM_ARG!"=="0" set "TAR_NAME=!IMAGE_NAME::=_!.tar"
)

call :apply_defaults "!SERVICE!"
if not defined IMAGE_NAME set "IMAGE_NAME=!DEFAULT_IMAGE!"
if not defined BUILD_CONTEXT set "BUILD_CONTEXT=!DEFAULT_CONTEXT!"
if not defined DOCKERFILE set "DOCKERFILE=!DEFAULT_DOCKERFILE!"
if not defined TAR_NAME set "TAR_NAME=!IMAGE_NAME::=_!.tar"

set "tmp="
set /p tmp=Compose 服务名 (默认 !COMPOSE_SERVICE!):
if not "!tmp!"=="" set "COMPOSE_SERVICE=!tmp!"
if not defined COMPOSE_SERVICE set "COMPOSE_SERVICE=!SERVICE!"

set "tmp="
set /p tmp=镜像名 (默认 !IMAGE_NAME!):
if not "!tmp!"=="" set "IMAGE_NAME=!tmp!"

set "tmp="
set /p tmp=构建目录 (默认 !BUILD_CONTEXT!):
if not "!tmp!"=="" set "BUILD_CONTEXT=!tmp!"

set "tmp="
set /p tmp=Dockerfile(可空, 默认 !DOCKERFILE!):
if not "!tmp!"=="" set "DOCKERFILE=!tmp!"

set "tmp="
set /p tmp=导出 tar 名称 (默认 !TAR_NAME!):
if not "!tmp!"=="" set "TAR_NAME=!tmp!"

set "tmp="
set /p tmp=服务器 IP (默认 !SERVER_IP!):
if not "!tmp!"=="" set "SERVER_IP=!tmp!"

set "tmp="
set /p tmp=服务器用户 (默认 !SERVER_USER!):
if not "!tmp!"=="" set "SERVER_USER=!tmp!"

set "tmp="
set /p tmp=远程路径 (默认 !REMOTE_PATH!):
if not "!tmp!"=="" set "REMOTE_PATH=!tmp!"

set "tmp="
set /p tmp=Compose 文件名 (默认 !COMPOSE_FILE!):
if not "!tmp!"=="" set "COMPOSE_FILE=!tmp!"

exit /b 0

:batch_process
echo ========================================
echo   批量构建和部署脚本
echo ========================================
echo 服务列表: !SERVICES!
echo 服务器: !SERVER_USER!@!SERVER_IP!
echo 远程路径: !REMOTE_PATH!
echo Compose 文件: !COMPOSE_FILE!
echo ========================================
echo.

set "TAR_FILES="
set "COMPOSE_SERVICES="

REM 步骤1: 批量构建所有镜像
echo [1/4] 正在批量构建所有镜像...
for %%s in (!SERVICES!) do (
  echo   构建服务: %%s
  call :apply_defaults "%%s"
  set "IMG=!DEFAULT_IMAGE!"
  set "CTX=!DEFAULT_CONTEXT!"
  set "DF=!DEFAULT_DOCKERFILE!"
  
  if not exist "!CTX!" (
    echo   [ERROR] 构建目录不存在: !CTX!
    exit /b 2
  )
  
  if defined DF (
    if "%DRY_RUN%"=="1" (
      echo   docker build -t !IMG! -f "!DF!" "!CTX!"
    ) else (
      docker build -t !IMG! -f "!DF!" "!CTX!"
      if !ERRORLEVEL! NEQ 0 (
        echo   [ERROR] 镜像构建失败: %%s
        exit /b !ERRORLEVEL!
      )
    )
  ) else (
    if "%DRY_RUN%"=="1" (
      echo   docker build -t !IMG! "!CTX!"
    ) else (
      docker build -t !IMG! "!CTX!"
      if !ERRORLEVEL! NEQ 0 (
        echo   [ERROR] 镜像构建失败: %%s
        exit /b !ERRORLEVEL!
      )
    )
  )
  echo   [OK] 构建成功: %%s
)

REM 步骤2: 批量导出所有镜像
echo.
echo [2/4] 正在批量导出所有镜像...
if not exist images mkdir images
for %%s in (!SERVICES!) do (
  call :apply_defaults "%%s"
  set "IMG=!DEFAULT_IMAGE!"
  set "TAR_FILE=!IMG::=_!.tar"
  echo   导出: !IMG! -^> images\!TAR_FILE!
  
  if "%DRY_RUN%"=="1" (
    echo   docker save -o "images\!TAR_FILE!" "!IMG!"
  ) else (
    docker save -o "images\!TAR_FILE!" "!IMG!"
    if !ERRORLEVEL! NEQ 0 (
      echo   [ERROR] 镜像导出失败: %%s
      exit /b !ERRORLEVEL!
    )
  )
  
  if defined TAR_FILES (
    set "TAR_FILES=!TAR_FILES! images\!TAR_FILE!"
  ) else (
    set "TAR_FILES=images\!TAR_FILE!"
  )
  
  if defined COMPOSE_SERVICES (
    set "COMPOSE_SERVICES=!COMPOSE_SERVICES! %%s"
  ) else (
    set "COMPOSE_SERVICES=%%s"
  )
)

REM 步骤3: 批量上传所有镜像
echo.
echo [3/4] 正在批量上传镜像到服务器 (需输入密码)...
echo   上传文件: !TAR_FILES!
if "%DRY_RUN%"=="1" (
  echo   scp !TAR_FILES! !SERVER_USER!@!SERVER_IP!:!REMOTE_PATH!/images/
) else (
  scp !TAR_FILES! !SERVER_USER!@!SERVER_IP!:!REMOTE_PATH!/images/
  if !ERRORLEVEL! NEQ 0 (
    echo   [ERROR] 文件上传失败
    exit /b !ERRORLEVEL!
  )
)
echo   [OK] 上传成功

REM 步骤4: 远程批量加载并部署
echo.
echo [4/4] 正在远程执行批量部署 (需再次输入密码)...

REM 构建加载命令
set "LOAD_CMD="
for %%s in (!SERVICES!) do (
  call :apply_defaults "%%s"
  set "IMG=!DEFAULT_IMAGE!"
  set "TAR_FILE=!IMG::=_!.tar"
  if defined LOAD_CMD (
    set "LOAD_CMD=!LOAD_CMD! && docker load -i !REMOTE_PATH!/images/!TAR_FILE!"
  ) else (
    set "LOAD_CMD=docker load -i !REMOTE_PATH!/images/!TAR_FILE!"
  )
)

set "REMOTE_CMD=mkdir -p !REMOTE_PATH!/images && !LOAD_CMD! && cd !REMOTE_PATH! && !COMPOSE_CMD! -f !COMPOSE_FILE! up -d !COMPOSE_SERVICES!"

echo   部署服务: !COMPOSE_SERVICES!
if "%DRY_RUN%"=="1" (
  echo   ssh !SERVER_USER!@!SERVER_IP! "!REMOTE_CMD!"
) else (
  ssh !SERVER_USER!@!SERVER_IP! "!REMOTE_CMD!"
  if !ERRORLEVEL! EQU 0 (
    echo ========================================
    echo   所有服务更新成功！
    echo ========================================
    echo 已部署服务: !COMPOSE_SERVICES!
  ) else (
    echo   [ERROR] 远程部署失败
    exit /b !ERRORLEVEL!
  )
)

exit /b 0

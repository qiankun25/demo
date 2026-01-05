# Frontend Dockerfile (多阶段构建 - 生产环境)
# 从项目根目录构建: docker build -f frontend/Dockerfile -t frontend:latest .

# 阶段 1: 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app

# 复制 package 文件
COPY frontend/package*.json ./

# 安装依赖
RUN npm ci --only=production=false

# 复制源代码
COPY frontend/ ./

# 构建应用（环境变量在构建时注入）
ARG VITE_API_BASE_URL
ARG VITE_MINIO_UPLOAD_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_MINIO_UPLOAD_URL=$VITE_MINIO_UPLOAD_URL

# 构建生产版本
RUN npm run build

# 阶段 2: Nginx 服务阶段
FROM nginx:alpine

# 复制构建产物到 Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]


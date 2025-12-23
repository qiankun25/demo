.PHONY: help dev prod build up down restart logs test clean health deploy

# 默认目标
help:
	@echo "Literature Download Service - 可用命令："
	@echo ""
	@echo "开发环境："
	@echo "  make dev          - 启动开发环境"
	@echo "  make logs         - 查看日志"
	@echo "  make restart      - 重启服务"
	@echo "  make down         - 停止服务"
	@echo "  make clean        - 停止服务并清理数据"
	@echo ""
	@echo "生产环境："
	@echo "  make prod         - 启动生产环境"
	@echo "  make deploy       - 运行部署脚本"
	@echo "  make health       - 健康检查"
	@echo ""
	@echo "测试："
	@echo "  make test         - 运行测试"
	@echo "  make test-cov     - 运行测试并生成覆盖率报告"
	@echo ""
	@echo "其他："
	@echo "  make build        - 构建镜像"
	@echo "  make shell        - 进入应用容器"
	@echo "  make db-shell     - 进入数据库"

# 开发环境
dev:
	docker-compose up -d
	@echo "开发环境已启动"
	@echo "API: http://localhost:8000"
	@echo "API 文档: http://localhost:8000/docs"
	@echo "MinIO 控制台: http://localhost:9001"

# 生产环境
prod:
	docker-compose -f docker-compose.prod.yml up -d
	@echo "生产环境已启动"

# 构建镜像
build:
	docker-compose build --no-cache

# 启动服务
up:
	docker-compose up -d

# 停止服务
down:
	docker-compose down

# 重启服务
restart:
	docker-compose restart

# 查看日志
logs:
	docker-compose logs -f

# 查看应用日志
logs-app:
	docker-compose logs -f app

# 查看 Celery 日志
logs-celery:
	docker-compose logs -f celery

# 运行测试
test:
	docker-compose run --rm app pytest

# 运行测试并生成覆盖率
test-cov:
	docker-compose run --rm app pytest --cov=app --cov-report=html
	@echo "覆盖率报告: htmlcov/index.html"

# 清理（停止并删除数据）
clean:
	docker-compose down -v
	@echo "服务已停止，数据已清理"

# 健康检查
health:
	@curl -f http://localhost:8000/health || echo "服务未运行"

# 部署脚本
deploy:
	@chmod +x scripts/deploy.sh
	@./scripts/deploy.sh

# 进入应用容器
shell:
	docker-compose exec app /bin/bash

# 进入数据库
db-shell:
	docker-compose exec db psql -U user -d downloads

# 扩展 worker
scale-workers:
	docker-compose up -d --scale celery=3
	@echo "已扩展到 3 个 Celery worker"

# 查看服务状态
status:
	docker-compose ps

# 初始化生产配置
init-prod:
	@if [ ! -f .env.production ]; then \
		cp .env.production.example .env.production; \
		echo "已创建 .env.production，请编辑配置"; \
	else \
		echo ".env.production 已存在"; \
	fi

# 备份数据库
backup-db:
	@mkdir -p backups
	docker-compose exec -T db pg_dump -U user downloads > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "数据库备份完成"

# 恢复数据库
restore-db:
	@if [ -z "$(FILE)" ]; then \
		echo "用法: make restore-db FILE=backups/backup_20231201_120000.sql"; \
	else \
		docker-compose exec -T db psql -U user downloads < $(FILE); \
		echo "数据库恢复完成"; \
	fi

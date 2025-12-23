-- 初始化数据库脚本
-- 在 PostgreSQL 容器启动时自动执行

-- 创建数据库（如果不存在）
-- 注意：此脚本在 docker-entrypoint-initdb.d 中执行时，数据库已由环境变量创建

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建索引以提高查询性能（表由 SQLAlchemy 创建后）
-- 这些索引会在应用首次启动时由 SQLAlchemy 创建

-- 设置时区
SET timezone = 'UTC';

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE literature_downloads TO prod_user;

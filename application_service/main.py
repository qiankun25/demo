from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers import auth, subscriptions, morning_report, literature_review, literature_search, literature_translation

# 注意：数据库表已存在，不需要自动创建
# 如果需要重新创建表，可以取消下面的注释
# from database import engine, Base
# Base.metadata.create_all(bind=engine)

# 创建 FastAPI 应用
app = FastAPI(
    title="ResearchGO API",
    description="ResearchGO 后端 API 服务",
    version="1.0.0"
)

# 配置 CORS - 开放所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有请求头
)

# 注册路由
app.include_router(auth.router)
app.include_router(subscriptions.router)
app.include_router(morning_report.router)
app.include_router(literature_review.router)
app.include_router(literature_search.router)
app.include_router(literature_translation.router)

# 挂载静态文件服务（用于访问上传的论文文件）
# 注意：在生产环境中，建议使用nginx等web服务器来提供静态文件服务
import os
from pathlib import Path
uploads_dir = Path("uploads/papers")
uploads_dir.mkdir(parents=True, exist_ok=True)

# 只在uploads目录存在时才挂载
if uploads_dir.exists():
    app.mount("/uploads/papers", StaticFiles(directory=str(uploads_dir)), name="papers")


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to ResearchGO API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


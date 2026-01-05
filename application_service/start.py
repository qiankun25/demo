"""
启动脚本
用于快速启动 FastAPI 服务
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式：自动重载
        log_level="info"
    )


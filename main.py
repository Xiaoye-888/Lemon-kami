"""
Lemon Kami - FastAPI 主应用入口
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from database import init_db
from routes_sdk import router as sdk_router
from routes_admin_advanced import router as admin_advanced_router
from routes_admin import router as admin_router
from routes_auth import router as auth_router
from routes_commercial import router as commercial_router
from routes_user import router as user_router
from routes_merchant import router as merchant_router
from routes_docs import router as docs_router
from config import settings

# 创建 logs 目录
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 生成日志文件名（带日期）
log_file = os.path.join(log_dir, f"lemon_kami_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志格式
log_format = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 根据 DEBUG 配置设置日志级别
if settings.DEBUG:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

# 配置根日志记录器
logger = logging.getLogger()
logger.setLevel(log_level)

# 清除已有的处理器
logger.handlers.clear()

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

# 文件处理器（自动轮转，最大 10MB，保留 5 个备份）
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(log_level)
file_handler.setFormatter(log_format)
logger.addHandler(file_handler)

# 获取应用日志记录器
app_logger = logging.getLogger("lemon_kami")


def get_cors_allowed_origins() -> list[str]:
    """Return configured CORS origins, allowing wildcard only for local debug."""
    raw_origins = settings.CORS_ALLOWED_ORIGINS.strip()
    if raw_origins:
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        if not settings.DEBUG:
            origins = [origin for origin in origins if origin != "*"]
        return origins
    if settings.DEBUG:
        return ["*"]
    return []

# 创建 FastAPI 应用
app = FastAPI(
    title="Lemon Kami API",
    description="小柠檬网络验证 - 多租户卡密分发与验证平台",
    version="1.0.0",
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_API_DOCS else None,
    debug=settings.DEBUG  # 控制是否显示调试信息
)

# 配置 CORS（跨域资源共享）
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SDK 文件路径配置
sdk_base_dir = os.path.join(os.path.dirname(__file__), "sdk")
sdk_files = {
    "python": os.path.join(sdk_base_dir, "python_sdk", "lemon-kami-python-sdk-1.0.0.zip"),
    "javascript": os.path.join(sdk_base_dir, "js_sdk", "lemon-kami-js-sdk-1.0.0.zip"),
    "java": os.path.join(sdk_base_dir, "java_sdk", "lemon-kami-java-sdk-1.0.0.zip")
}

# 下载 SDK 文件接口
@app.get("/api/sdk/download", tags=["SDK Download"])
async def download_sdk(type: str):
    """下载 SDK 文件"""
    if type not in sdk_files:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="SDK 类型不存在")
    
    file_path = sdk_files[type]
    if not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="SDK 文件不存在")
    
    filenames = {
        "python": "lemon-kami-python-sdk-1.0.0.zip",
        "javascript": "lemon-kami-js-sdk-1.0.0.zip",
        "java": "lemon-kami-java-sdk-1.0.0.zip"
    }
    
    return FileResponse(
        path=file_path,
        filename=filenames[type],
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filenames[type]}"
        }
    )

app_logger.info(f"✅ SDK download endpoint configured")

# 注册路由
app.include_router(sdk_router)
app.include_router(auth_router)
app.include_router(admin_advanced_router)
app.include_router(commercial_router)
app.include_router(admin_router)
app.include_router(user_router)
app.include_router(merchant_router)
app.include_router(docs_router)


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    init_db()
    app_logger.info("✅ Database initialized successfully")
    app_logger.info(f"Application started in {'DEBUG' if settings.DEBUG else 'PRODUCTION'} mode")
    app_logger.info(f"Log file: {log_file}")


@app.get("/", tags=["Root"])
async def root():
    """根路径"""
    payload = {
        "message": "Welcome to Lemon Kami API",
        "public_docs": "/docs/api#basic-info",
    }
    if settings.ENABLE_API_DOCS:
        payload.update({"docs": "/docs", "redoc": "/redoc"})
    return payload


@app.get("/health", tags=["Health"])
async def health_check():
    """健康检查接口"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

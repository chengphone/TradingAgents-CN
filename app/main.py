"""
TradingAgents-CN 微信小程序版 FastAPI Backend
精简版 - 仅保留核心股票分析功能
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.logging_config import setup_logging
from app.routers import health, analysis, reports, config as config_router
from app.routers import wechat_auth
from app.routers import system_config as system_config_router
from app.middleware.request_id import RequestIDMiddleware


def get_version() -> str:
    try:
        version_file = Path(__file__).parent.parent / "VERSION"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "1.0.0-mini"


async def _print_config_summary(logger):
    logger.info("=" * 60)
    logger.info("TradingAgents-CN 微信小程序版 启动中")
    logger.info("=" * 60)
    logger.info(f"Environment: {'Production' if settings.is_production else 'Development'}")
    logger.info(f"CloudBase: {'已配置' if settings.WECHAT_APPID else '未配置'}")
    logger.info(f"微信小程序 AppID: {settings.WECHAT_APPID[:8]}..." if settings.WECHAT_APPID else "微信小程序 AppID: 未配置")
    logger.info("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = logging.getLogger("app.main")

    await init_db()

    # 配置桥接：将 LLM 配置写入环境变量，供 tradingagents 引擎使用
    try:
        from app.core.config_bridge import bridge_config_to_env
        bridge_config_to_env()
    except Exception as e:
        logger.warning(f"配置桥接失败: {e}")

    await _print_config_summary(logger)
    logger.info("TradingAgents 微信小程序版后端已启动")

    yield

    await close_db()
    logger.info("TradingAgents 后端已停止")


app = FastAPI(
    title="TradingAgents-CN 微信小程序 API",
    description="AI股票分析 · 微信小程序版",
    version=get_version(),
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Request ID 中间件
app.add_middleware(RequestIDMiddleware)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    if request.url.path in ["/health", "/favicon.ico"]:
        return await call_next(request)

    logger = logging.getLogger("webapi")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({process_time:.3f}s)")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "服务器内部错误"}},
    )


# ---- 路由注册（仅核心） ----

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(wechat_auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(reports.router, tags=["reports"])
app.include_router(config_router.router, prefix="/api", tags=["config"])
app.include_router(system_config_router.router, prefix="/api/system", tags=["system"])


@app.get("/")
async def root():
    return {
        "name": "TradingAgents-CN 微信小程序 API",
        "version": get_version(),
        "status": "running",
        "docs_url": "/docs" if settings.DEBUG else None,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )

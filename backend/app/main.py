import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ExceptionHandler

from app.api.v1 import api_router, websocket
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.exceptions import APIException, api_exception_handler
from app.core.minio_client import init_minio
from app.core.redis_client import close_redis, init_redis
from app.workers import start_scheduler, stop_scheduler

settings = get_settings()
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    await init_redis()
    init_minio()
    start_scheduler()
    yield
    stop_scheduler()
    await close_redis()
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="去中心化AI算力共享市场后端 API",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(APIException, cast(ExceptionHandler, api_exception_handler))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": 1000,
            "message": "系统错误",
            "data": str(exc) if settings.DEBUG else None,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
# WebSocket 端点单独注册：不经过 HTTP 首次部署守卫，自身已通过 token 鉴权
app.include_router(websocket.router, prefix=settings.API_V1_PREFIX)

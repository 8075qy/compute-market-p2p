from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models import Base
from app.services.gpu_spec import seed_gpu_specs

settings = get_settings()

_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "echo": settings.DEBUG,
}
if settings.DEBUG:
    # 开发环境使用 NullPool，避免 reload 时连接泄漏
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
    _engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncIterator[AsyncSession]:
    """Context manager for database session outside of FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection and create tables if not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 预置 GPU 规格库等基础数据（幂等）
    async with AsyncSessionLocal() as session:
        await seed_gpu_specs(session)


async def close_db() -> None:
    """Close database connection."""
    await engine.dispose()

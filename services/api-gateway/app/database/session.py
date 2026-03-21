"""Database session management with async SQLAlchemy"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import structlog

from app.config import get_settings

logger = structlog.get_logger()

engine = None
async_session_factory = None


class Base(DeclarativeBase):
    pass


async def init_db():
    global engine, async_session_factory
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        echo=settings.neuranac_env == "development",
    )
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.info("Database initialized", host=settings.postgres_host)


async def close_db():
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


def get_pool_status() -> dict:
    """Return connection pool statistics for monitoring (G36)."""
    if engine is None:
        return {"status": "not_initialized"}
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.status(),
    }


def get_async_engine():
    """Return the async engine instance (or None if not initialized)."""
    return engine


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

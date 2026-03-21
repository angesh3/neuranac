"""Shared test fixtures for API Gateway tests"""
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Set test environment BEFORE any app imports
os.environ.setdefault("NeuraNAC_ENV", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "neuranac_test")
os.environ.setdefault("POSTGRES_USER", "neuranac")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_PASSWORD", "")

from app.database.session import get_db
from app.database.redis import get_redis
from app.main import app


def _mock_db_session():
    """Create a mock async DB session with common methods"""
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=0)
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    result_mock.fetchall = MagicMock(return_value=[])
    result_mock.fetchone = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result_mock)
    db.get = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.delete = AsyncMock()
    return db


def _mock_redis_client():
    """Create a mock async Redis client"""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    return redis


# Override get_db dependency globally for all tests
async def override_get_db():
    yield _mock_db_session()

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Mock async database session"""
    return _mock_db_session()


@pytest.fixture
def mock_redis():
    """Mock async Redis client"""
    return _mock_redis_client()

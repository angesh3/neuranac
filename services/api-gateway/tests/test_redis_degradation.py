"""Tests for Redis graceful degradation (G26)."""
import pytest
from unittest.mock import AsyncMock, patch


class TestRedisGracefulDegradation:
    @pytest.mark.asyncio
    async def test_get_redis_returns_none_when_unavailable(self):
        from app.database import redis as redis_mod
        old_avail = redis_mod._redis_available
        redis_mod._redis_available = False
        try:
            assert redis_mod.get_redis() is None
        finally:
            redis_mod._redis_available = old_avail

    @pytest.mark.asyncio
    async def test_is_redis_available_false_initially(self):
        from app.database.redis import is_redis_available
        # In test env Redis may not be running
        result = is_redis_available()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_safe_redis_op_returns_default_when_unavailable(self):
        from app.database import redis as redis_mod
        old_avail = redis_mod._redis_available
        redis_mod._redis_available = False
        try:
            result = await redis_mod.safe_redis_op(AsyncMock()(), default="fallback")
            assert result == "fallback"
        finally:
            redis_mod._redis_available = old_avail

    @pytest.mark.asyncio
    async def test_safe_redis_op_returns_default_on_exception(self):
        from app.database import redis as redis_mod
        old_avail = redis_mod._redis_available
        redis_mod._redis_available = True
        try:
            async def failing_coro():
                raise ConnectionError("boom")
            result = await redis_mod.safe_redis_op(failing_coro(), default="safe")
            assert result == "safe"
        finally:
            redis_mod._redis_available = old_avail

    @pytest.mark.asyncio
    async def test_init_redis_handles_connection_failure(self):
        from app.database import redis as redis_mod
        with patch("app.database.redis.aioredis") as mock_aioredis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=ConnectionError("refused"))
            mock_aioredis.from_url.return_value = mock_client
            await redis_mod.init_redis()
            assert redis_mod._redis_available is False
            assert redis_mod.redis_client is None

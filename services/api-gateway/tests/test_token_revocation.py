"""Tests for token revocation (G24)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestRevokeUserTokens:
    @pytest.mark.asyncio
    async def test_revoke_no_redis_returns_silently(self):
        with patch("app.database.redis.get_redis", return_value=None):
            from app.middleware.auth import revoke_user_tokens
            await revoke_user_tokens("user-123")  # should not raise

    @pytest.mark.asyncio
    async def test_revoke_deletes_families_and_blocklists(self):
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock()

        mock_rdb = AsyncMock()
        mock_rdb.smembers = AsyncMock(return_value={"fam-1", "fam-2"})
        mock_rdb.smembers.side_effect = [
            {"fam-1", "fam-2"},   # user_rt_families:user-1
            {"jti-a", "jti-b"},   # rt_family:fam-1
            {"jti-c"},            # rt_family:fam-2
        ]
        mock_rdb.delete = AsyncMock()
        mock_rdb.setex = AsyncMock()
        mock_rdb.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.database.redis.get_redis", return_value=mock_rdb):
            from app.middleware.auth import revoke_user_tokens
            await revoke_user_tokens("user-1")

        # Pipeline should have had delete calls queued
        assert mock_pipe.delete.call_count >= 3
        # Should have set user_blocked:user-1
        mock_rdb.setex.assert_called()


class TestStoreRefreshTokenIndex:
    @pytest.mark.asyncio
    async def test_store_adds_family_to_user_index(self):
        mock_rdb = AsyncMock()
        mock_rdb.setex = AsyncMock()
        mock_rdb.sadd = AsyncMock()
        mock_rdb.expire = AsyncMock()

        with patch("app.database.redis.get_redis", return_value=mock_rdb):
            from app.middleware.auth import store_refresh_token
            await store_refresh_token("jti-1", "fam-1", "user-1", ttl_days=7)

        # Should sadd to user_rt_families:user-1
        calls = [str(c) for c in mock_rdb.sadd.call_args_list]
        assert any("user_rt_families:user-1" in c for c in calls)

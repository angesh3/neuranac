"""Tests for NLToSQL — pattern matching, safety checks, and query generation."""
import pytest
from app.nl_to_sql import NLToSQL, QUERY_PATTERNS, FORBIDDEN_SQL


@pytest.fixture
def nl2sql():
    return NLToSQL()


class TestPatternMatching:
    def test_session_count_pattern(self, nl2sql):
        sql, desc = nl2sql._pattern_match("how many sessions are there?")
        assert sql is not None
        assert "auth_sessions" in sql
        assert "COUNT" in sql

    def test_active_sessions_pattern(self, nl2sql):
        sql, desc = nl2sql._pattern_match("show active sessions")
        assert sql is not None
        assert "ended_at IS NULL" in sql

    def test_failed_auth_pattern(self, nl2sql):
        sql, desc = nl2sql._pattern_match("show failed authentications")
        assert sql is not None
        assert "reject" in sql

    def test_endpoint_count_pattern(self, nl2sql):
        sql, desc = nl2sql._pattern_match("how many endpoints?")
        assert sql is not None
        assert "endpoints" in sql

    def test_expired_certs_pattern(self, nl2sql):
        sql, desc = nl2sql._pattern_match("show expiring certificates")
        assert sql is not None
        assert "certificates" in sql

    def test_vendor_distribution_pattern(self, nl2sql):
        sql, desc = nl2sql._pattern_match("top endpoint vendors")
        assert sql is not None
        assert "vendor" in sql

    def test_shadow_ai_pattern(self, nl2sql):
        sql, desc = nl2sql._pattern_match("show shadow AI detections")
        assert sql is not None
        assert "ai_data_flow_detections" in sql

    def test_no_match(self, nl2sql):
        sql, desc = nl2sql._pattern_match("xyzzy gibberish nonsense")
        assert sql is None
        assert desc is None


class TestSafetyChecks:
    def test_blocks_insert(self):
        assert FORBIDDEN_SQL.search("INSERT INTO users VALUES (1)")

    def test_blocks_delete(self):
        assert FORBIDDEN_SQL.search("DELETE FROM sessions")

    def test_blocks_drop(self):
        assert FORBIDDEN_SQL.search("DROP TABLE users")

    def test_blocks_update(self):
        assert FORBIDDEN_SQL.search("UPDATE sessions SET ended_at = NOW()")

    def test_allows_select(self):
        assert not FORBIDDEN_SQL.search("SELECT COUNT(*) FROM auth_sessions")

    def test_blocks_truncate(self):
        assert FORBIDDEN_SQL.search("TRUNCATE audit_log")


class TestTranslateAndExecute:
    @pytest.mark.asyncio
    async def test_no_match_returns_suggestions(self, nl2sql):
        result = await nl2sql.translate_and_execute("xyzzy gibberish")
        assert result["status"] == "no_match"
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_matched_query_without_db(self, nl2sql):
        result = await nl2sql.translate_and_execute("how many sessions?")
        # No DB connected → preview mode
        assert result["status"] == "preview"
        assert "sql" in result

    @pytest.mark.asyncio
    async def test_query_patterns_count(self):
        assert len(QUERY_PATTERNS) >= 18

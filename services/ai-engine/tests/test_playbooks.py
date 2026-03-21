"""Tests for PlaybookEngine — listing, creation, execution, stats."""
import pytest
from app.playbooks import PlaybookEngine, PlaybookStatus, BUILTIN_PLAYBOOKS


@pytest.fixture
def engine():
    return PlaybookEngine()


class TestListPlaybooks:
    def test_builtin_count(self, engine):
        playbooks = engine.list_playbooks()
        assert len(playbooks) == len(BUILTIN_PLAYBOOKS)

    def test_builtin_fields(self, engine):
        playbooks = engine.list_playbooks()
        for pb in playbooks:
            assert "id" in pb
            assert "name" in pb
            assert "description" in pb
            assert "severity" in pb
            assert "step_count" in pb
            assert pb["is_custom"] is False

    def test_get_builtin_playbook(self, engine):
        pb = engine.get_playbook("pb-auth-failure-lockout")
        assert pb is not None
        assert pb["name"] == "Auth Failure Lockout"
        assert len(pb["steps"]) > 0

    def test_get_nonexistent_playbook(self, engine):
        assert engine.get_playbook("nonexistent") is None


class TestCreatePlaybook:
    def test_create_custom(self, engine):
        result = engine.create_playbook(
            "pb-custom-1", "Custom Test", "A test playbook",
            "manual", "low",
            [{"action": "log_incident", "params": {"msg": "test"}}]
        )
        assert result["status"] == "created"
        pb = engine.get_playbook("pb-custom-1")
        assert pb is not None
        assert pb["name"] == "Custom Test"

    def test_custom_appears_in_list(self, engine):
        engine.create_playbook("pb-custom-2", "Custom 2", "desc", "manual", "low", [])
        playbooks = engine.list_playbooks()
        custom_count = sum(1 for p in playbooks if p["is_custom"])
        assert custom_count == 1


class TestExecution:
    @pytest.mark.asyncio
    async def test_execute_builtin(self, engine):
        result = await engine.execute(
            "pb-auth-failure-lockout",
            {"endpoint_mac": "AA:BB:CC:DD:EE:FF", "username": "jdoe"}
        )
        assert result["playbook_id"] == "pb-auth-failure-lockout"
        assert result["status"] == PlaybookStatus.COMPLETED
        assert len(result["steps_completed"]) > 0
        assert len(result["steps_failed"]) == 0
        assert result["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_execute_all_builtins(self, engine):
        for pb_id in BUILTIN_PLAYBOOKS:
            result = await engine.execute(pb_id, {"endpoint_mac": "AA:BB:CC:DD:EE:FF"})
            assert result["status"] in (PlaybookStatus.COMPLETED, PlaybookStatus.FAILED)

    @pytest.mark.asyncio
    async def test_execute_nonexistent(self, engine):
        result = await engine.execute("nonexistent", {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_executions_logged(self, engine):
        await engine.execute("pb-auth-failure-lockout", {"mac": "AA:BB:CC:DD:EE:FF"})
        execs = engine.get_executions()
        assert len(execs) == 1


class TestStats:
    @pytest.mark.asyncio
    async def test_stats_initial(self, engine):
        stats = engine.get_stats()
        assert stats["builtin_count"] == len(BUILTIN_PLAYBOOKS)
        assert stats["custom_count"] == 0
        assert stats["total_executions"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_execution(self, engine):
        await engine.execute("pb-auth-failure-lockout", {"mac": "test"})
        stats = engine.get_stats()
        assert stats["total_executions"] == 1
        assert stats["completed"] == 1
        assert stats["success_rate"] == 1.0

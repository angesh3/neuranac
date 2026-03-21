"""
Integration tests for AI Engine modules.
Tests cross-module interactions without external dependencies.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/ai-engine"))

from app.action_router import ActionRouter
from app.rag_troubleshooter import RAGTroubleshooter
from app.tls_fingerprint import TLSFingerprinter
from app.playbooks import PlaybookEngine
from app.capacity_planner import CapacityPlanner
from app.model_registry import ModelRegistry
from app.adaptive_risk import AdaptiveRiskEngine
from app.nl_to_sql import NLToSQL


class TestActionRouterIntegration:
    @pytest.mark.asyncio
    async def test_route_and_fallback_flow(self):
        router = ActionRouter()
        # Known intent
        result = await router.route("show system status")
        assert result["type"] in ("api_result", "error", "navigation", "text")
        assert "intent" in result

        # Unknown intent → fallback
        result = await router.route("xyzzy unknown command 42")
        assert result["type"] == "text"
        assert result["intent"] == "unknown"

    @pytest.mark.asyncio
    async def test_navigation_intents_cover_all_pages(self):
        router = ActionRouter()
        pages = ["/policies", "/network-devices", "/endpoints", "/sessions",
                 "/legacy-nac", "/diagnostics", "/settings"]
        for page in pages:
            found = False
            for nav_id, nav in router.nav_intents.items():
                if nav["route"] == page:
                    found = True
                    break
            assert found, f"No navigation intent for {page}"


class TestTroubleshooterIntegration:
    @pytest.mark.asyncio
    async def test_troubleshoot_with_retrieval(self):
        rag = RAGTroubleshooter()
        result = await rag.troubleshoot("EAP-TLS authentication failure expired certificate")
        assert "root_cause" in result
        assert result["kb_docs_retrieved"] > 0

    @pytest.mark.asyncio
    async def test_troubleshoot_unknown_issue(self):
        rag = RAGTroubleshooter()
        result = await rag.troubleshoot("completely unknown issue xyzzy")
        assert "root_cause" in result
        assert "recommended_fixes" in result


class TestTLSAndPlaybookIntegration:
    @pytest.mark.asyncio
    async def test_tls_detection_triggers_playbook(self):
        """Simulate: TLS fingerprint detects AI service → playbook responds."""
        fp = TLSFingerprinter()
        engine = PlaybookEngine()

        # Detect shadow AI
        detection = fp.analyze_ja3(
            "cd08e31494f9531f560d64c695473da9",
            endpoint_mac="AA:BB:CC:DD:EE:FF"
        )
        assert detection["is_ai_service"]

        # Execute playbook in response
        result = await engine.execute("pb-shadow-ai-block", {
            "endpoint_mac": detection["endpoint_mac"],
            "service": detection["service"],
        })
        assert result["status"] == "completed"
        assert len(result["steps_completed"]) > 0


class TestCapacityAndRegistryIntegration:
    @pytest.mark.asyncio
    async def test_capacity_forecasting_pipeline(self):
        planner = CapacityPlanner()
        import time
        base_ts = time.time() - 7200
        for i in range(30):
            await planner.record_metric("auth_rate_per_sec", 100.0 + i * 10, ts=base_ts + i * 240)

        result = await planner.forecast("auth_rate_per_sec", horizon_hours=24)
        assert result["status"] == "ok"
        assert result["forecast_value"] > 0

    @pytest.mark.asyncio
    async def test_model_registry_selection(self):
        registry = ModelRegistry()
        registry.register_model("profiler", "v1", "profiler", "http://a", weight=1.0)
        registry.register_model("profiler", "v2", "profiler", "http://b", weight=2.0)

        # Should select one of the two models
        model = registry.select_model("profiler")
        assert model is not None
        assert model.model_type == "profiler"


class TestAdaptiveRiskIntegration:
    @pytest.mark.asyncio
    async def test_feedback_loop_and_calibration(self):
        engine = AdaptiveRiskEngine()

        # Record enough feedback to trigger calibration
        for i in range(25):
            await engine.record_feedback("t1", 75, "quarantine", True)
        for i in range(5):
            await engine.record_feedback("t1", 55, "quarantine", False)

        stats = await engine.get_stats("t1")
        assert stats["feedback_count"] == 30
        assert stats["accuracy"] > 0.5


class TestNLToSQLIntegration:
    @pytest.mark.asyncio
    async def test_translate_without_db(self):
        nl2sql = NLToSQL()
        result = await nl2sql.translate_and_execute("how many active sessions?")
        assert result["status"] == "preview"
        assert "SELECT" in result["sql"]

    @pytest.mark.asyncio
    async def test_safety_blocks_writes(self):
        nl2sql = NLToSQL()
        # Pattern-matched query should be SELECT only
        sql, _ = nl2sql._pattern_match("how many sessions?")
        assert sql is not None
        assert "INSERT" not in sql.upper()
        assert "DELETE" not in sql.upper()

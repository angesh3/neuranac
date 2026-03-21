"""Tests for ModelRegistry — registration, selection, A/B experiments."""
import pytest
from app.model_registry import ModelRegistry, ModelVersion, ABExperiment


@pytest.fixture
def registry():
    return ModelRegistry()


class TestModelRegistration:
    def test_register_model(self, registry):
        result = registry.register_model("profiler", "v1", "profiler", "http://localhost:8081/profile")
        assert result["status"] == "registered"
        assert result["model_id"] == "profiler-v1"

    def test_get_model(self, registry):
        registry.register_model("profiler", "v1", "profiler", "http://localhost:8081/profile")
        model = registry.get_model("profiler-v1")
        assert model is not None
        assert model.name == "profiler"
        assert model.version == "v1"

    def test_get_nonexistent(self, registry):
        assert registry.get_model("nonexistent") is None

    def test_deactivate_model(self, registry):
        registry.register_model("risk", "v1", "risk", "http://localhost:8081/risk")
        result = registry.deactivate_model("risk-v1")
        assert result["status"] == "deactivated"
        model = registry.get_model("risk-v1")
        assert model.is_active is False

    def test_deactivate_nonexistent(self, registry):
        result = registry.deactivate_model("nonexistent")
        assert result["status"] == "not_found"

    def test_list_models(self, registry):
        registry.register_model("profiler", "v1", "profiler", "http://a")
        registry.register_model("risk", "v1", "risk", "http://b")
        models = registry.list_models()
        assert len(models) == 2

    def test_list_models_by_type(self, registry):
        registry.register_model("profiler", "v1", "profiler", "http://a")
        registry.register_model("risk", "v1", "risk", "http://b")
        profilers = registry.list_models(model_type="profiler")
        assert len(profilers) == 1
        assert profilers[0]["model_type"] == "profiler"


class TestModelVersion:
    def test_record_prediction(self):
        mv = ModelVersion("test-v1", "test", "v1", "profiler", "http://a")
        mv.record_prediction(10.5, True)
        mv.record_prediction(15.0, False)
        stats = mv.get_stats()
        assert stats["predictions"] == 2
        assert stats["errors"] == 1
        assert stats["error_rate"] == 0.5

    def test_latency_stats(self):
        mv = ModelVersion("test-v1", "test", "v1", "profiler", "http://a")
        for lat in [10.0, 20.0, 30.0, 40.0, 50.0]:
            mv.record_prediction(lat, True)
        stats = mv.get_stats()
        assert stats["avg_latency_ms"] == 30.0
        assert stats["p95_latency_ms"] > 0


class TestModelSelection:
    def test_select_no_candidates(self, registry):
        assert registry.select_model("profiler") is None

    def test_select_returns_active(self, registry):
        registry.register_model("profiler", "v1", "profiler", "http://a")
        model = registry.select_model("profiler")
        assert model is not None
        assert model.model_type == "profiler"

    def test_select_skips_inactive(self, registry):
        registry.register_model("profiler", "v1", "profiler", "http://a")
        registry.deactivate_model("profiler-v1")
        assert registry.select_model("profiler") is None


class TestABExperiment:
    def test_create_experiment(self, registry):
        registry.register_model("profiler", "v1", "profiler", "http://a")
        registry.register_model("profiler", "v2", "profiler", "http://b")
        result = registry.create_experiment("Test AB", "profiler-v1", "profiler-v2", 0.5)
        assert result["status"] == "created"
        assert "experiment_id" in result

    def test_create_experiment_missing_model(self, registry):
        result = registry.create_experiment("Test", "nonexistent-a", "nonexistent-b")
        assert result["status"] == "error"

    def test_stop_experiment(self, registry):
        registry.register_model("p", "v1", "profiler", "http://a")
        registry.register_model("p", "v2", "profiler", "http://b")
        create_result = registry.create_experiment("Test", "p-v1", "p-v2")
        exp_id = create_result["experiment_id"]
        stop_result = registry.stop_experiment(exp_id)
        assert stop_result["status"] == "stopped"

    def test_stop_nonexistent(self, registry):
        result = registry.stop_experiment("nonexistent")
        assert result["status"] == "not_found"

    def test_list_experiments(self, registry):
        registry.register_model("p", "v1", "profiler", "http://a")
        registry.register_model("p", "v2", "profiler", "http://b")
        registry.create_experiment("Test", "p-v1", "p-v2")
        exps = registry.list_experiments()
        assert len(exps) == 1

    def test_experiment_routing(self):
        exp = ABExperiment("exp-1", "Test", "model-a", "model-b", 0.5)
        results = set()
        for _ in range(100):
            results.add(exp.route_request())
        # Both models should be selected at least once with 50/50 split
        assert "model-a" in results
        assert "model-b" in results

    def test_experiment_no_winner_insufficient_data(self):
        exp = ABExperiment("exp-1", "Test", "model-a", "model-b", 0.5)
        for _ in range(10):
            exp.record_result("model-a", 10.0, True)
            exp.record_result("model-b", 15.0, True)
        summary = exp.get_summary()
        assert summary["winner"] is None  # Not enough data (<30)


class TestRegistryStats:
    def test_stats(self, registry):
        registry.register_model("p", "v1", "profiler", "http://a")
        registry.register_model("r", "v1", "risk", "http://b")
        stats = registry.get_stats()
        assert stats["total_models"] == 2
        assert stats["active_models"] == 2
        assert set(stats["model_types"]) == {"profiler", "risk"}

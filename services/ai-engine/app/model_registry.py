"""
Multi-Model Inference Pipeline & A/B Testing Registry.
Manages multiple AI model versions, routes inference requests between them,
and tracks performance metrics for A/B comparison.
"""
import os
import time
import uuid
import random
import numpy as np
import structlog
from collections import defaultdict
from typing import Dict, Any, List, Optional

logger = structlog.get_logger()

MODEL_PATH = os.getenv("AI_MODEL_PATH", "/data/models")


class OnnxModelRunner:
    """Loads and runs inference on an ONNX model via onnxruntime."""

    def __init__(self, onnx_path: str):
        self.onnx_path = onnx_path
        self._session = None
        self._loaded = False
        self._load_error: Optional[str] = None

    def load(self) -> bool:
        """Load the ONNX model. Returns True on success."""
        if self._loaded:
            return True
        try:
            import onnxruntime as ort
            if not os.path.isfile(self.onnx_path):
                self._load_error = f"ONNX file not found: {self.onnx_path}"
                logger.warning("ONNX model file missing", path=self.onnx_path)
                return False
            self._session = ort.InferenceSession(
                self.onnx_path,
                providers=["CPUExecutionProvider"],
            )
            self._loaded = True
            logger.info("ONNX model loaded", path=self.onnx_path)
            return True
        except ImportError:
            self._load_error = "onnxruntime not installed"
            logger.warning("onnxruntime not available — ONNX inference disabled")
            return False
        except Exception as e:
            self._load_error = str(e)
            logger.error("ONNX model load failed", error=str(e), path=self.onnx_path)
            return False

    def predict(self, features: List[float]) -> Dict[str, Any]:
        """Run inference on a feature vector. Returns predicted label index and probabilities."""
        if not self._loaded or self._session is None:
            return {"error": self._load_error or "Model not loaded"}
        try:
            input_name = self._session.get_inputs()[0].name
            arr = np.array([features], dtype=np.float32)
            outputs = self._session.run(None, {input_name: arr})
            label = int(outputs[0][0])
            probabilities = None
            if len(outputs) > 1:
                probabilities = outputs[1][0]
                if hasattr(probabilities, "tolist"):
                    probabilities = probabilities.tolist()
            return {"label": label, "probabilities": probabilities}
        except Exception as e:
            return {"error": str(e)}

    def get_info(self) -> Dict[str, Any]:
        """Return metadata about the loaded model."""
        info: Dict[str, Any] = {
            "onnx_path": self.onnx_path,
            "loaded": self._loaded,
            "error": self._load_error,
        }
        if self._session:
            info["inputs"] = [
                {"name": i.name, "shape": i.shape, "type": i.type}
                for i in self._session.get_inputs()
            ]
            info["outputs"] = [
                {"name": o.name, "shape": o.shape, "type": o.type}
                for o in self._session.get_outputs()
            ]
        return info


class ModelVersion:
    """Represents a registered model version."""
    def __init__(self, model_id: str, name: str, version: str, model_type: str,
                 endpoint: str, weight: float = 1.0, metadata: Optional[Dict] = None,
                 onnx_path: Optional[str] = None):
        self.model_id = model_id
        self.name = name
        self.version = version
        self.model_type = model_type  # profiler, risk, anomaly, nlp, etc.
        self.endpoint = endpoint
        self.weight = weight
        self.metadata = metadata or {}
        self.registered_at = time.time()
        self.is_active = True
        self._latencies: List[float] = []
        self._predictions: int = 0
        self._errors: int = 0
        self.onnx_runner: Optional[OnnxModelRunner] = None
        if onnx_path:
            self.onnx_runner = OnnxModelRunner(onnx_path)
            self.onnx_runner.load()

    def record_prediction(self, latency_ms: float, success: bool):
        self._predictions += 1
        self._latencies.append(latency_ms)
        if not success:
            self._errors += 1
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-1000:]

    def get_stats(self) -> Dict[str, Any]:
        avg_latency = sum(self._latencies) / max(len(self._latencies), 1)
        p95_latency = sorted(self._latencies)[int(len(self._latencies) * 0.95)] if self._latencies else 0
        return {
            "model_id": self.model_id,
            "name": self.name,
            "version": self.version,
            "model_type": self.model_type,
            "endpoint": self.endpoint,
            "weight": self.weight,
            "is_active": self.is_active,
            "predictions": self._predictions,
            "errors": self._errors,
            "error_rate": round(self._errors / max(self._predictions, 1), 4),
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "registered_at": self.registered_at,
        }


class ABExperiment:
    """Tracks an A/B test between two model versions."""
    def __init__(self, experiment_id: str, name: str,
                 model_a_id: str, model_b_id: str, traffic_split: float = 0.5):
        self.experiment_id = experiment_id
        self.name = name
        self.model_a_id = model_a_id
        self.model_b_id = model_b_id
        self.traffic_split = traffic_split  # fraction going to model_b
        self.created_at = time.time()
        self.is_active = True
        self.results_a: List[Dict] = []
        self.results_b: List[Dict] = []

    def route_request(self) -> str:
        """Decide which model to route to based on traffic split."""
        return self.model_b_id if random.random() < self.traffic_split else self.model_a_id

    def record_result(self, model_id: str, latency_ms: float, success: bool,
                       feedback_correct: Optional[bool] = None):
        entry = {"latency_ms": latency_ms, "success": success,
                 "feedback_correct": feedback_correct, "timestamp": time.time()}
        if model_id == self.model_a_id:
            self.results_a.append(entry)
        else:
            self.results_b.append(entry)

    def get_summary(self) -> Dict[str, Any]:
        def _stats(results):
            if not results:
                return {"count": 0, "success_rate": 0, "avg_latency_ms": 0, "accuracy": None}
            successes = sum(1 for r in results if r["success"])
            latencies = [r["latency_ms"] for r in results]
            feedback = [r for r in results if r.get("feedback_correct") is not None]
            correct = sum(1 for f in feedback if f["feedback_correct"]) if feedback else None
            return {
                "count": len(results),
                "success_rate": round(successes / len(results), 4),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
                "accuracy": round(correct / len(feedback), 4) if feedback and correct is not None else None,
            }
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "is_active": self.is_active,
            "traffic_split": self.traffic_split,
            "model_a": {"id": self.model_a_id, **_stats(self.results_a)},
            "model_b": {"id": self.model_b_id, **_stats(self.results_b)},
            "winner": self._determine_winner(),
        }

    def _determine_winner(self) -> Optional[str]:
        if len(self.results_a) < 30 or len(self.results_b) < 30:
            return None  # Not enough data
        stats_a = self.get_summary()["model_a"]
        stats_b = self.get_summary()["model_b"]
        # Winner = higher accuracy (if available) or higher success rate with lower latency
        if stats_a.get("accuracy") is not None and stats_b.get("accuracy") is not None:
            if stats_a["accuracy"] > stats_b["accuracy"] + 0.05:
                return self.model_a_id
            elif stats_b["accuracy"] > stats_a["accuracy"] + 0.05:
                return self.model_b_id
        if stats_a["success_rate"] > stats_b["success_rate"] + 0.05:
            return self.model_a_id
        elif stats_b["success_rate"] > stats_a["success_rate"] + 0.05:
            return self.model_b_id
        return None  # No clear winner yet


class ModelRegistry:
    """Central registry for AI models, versions, and A/B experiments."""

    def __init__(self):
        self._models: Dict[str, ModelVersion] = {}
        self._experiments: Dict[str, ABExperiment] = {}

    def register_model(self, name: str, version: str, model_type: str,
                        endpoint: str, weight: float = 1.0,
                        metadata: Optional[Dict] = None,
                        onnx_path: Optional[str] = None) -> Dict[str, Any]:
        """Register a new model version, optionally loading an ONNX model."""
        model_id = f"{name}-{version}"
        mv = ModelVersion(model_id, name, version, model_type, endpoint, weight, metadata, onnx_path)
        self._models[model_id] = mv
        onnx_loaded = mv.onnx_runner.get_info() if mv.onnx_runner else None
        logger.info("Model registered", model_id=model_id, type=model_type,
                    endpoint=endpoint, onnx=onnx_loaded is not None)
        return {"status": "registered", "model_id": model_id, "onnx": onnx_loaded}

    def deactivate_model(self, model_id: str) -> Dict[str, Any]:
        if model_id in self._models:
            self._models[model_id].is_active = False
            return {"status": "deactivated", "model_id": model_id}
        return {"status": "not_found"}

    def get_model(self, model_id: str) -> Optional[ModelVersion]:
        return self._models.get(model_id)

    def list_models(self, model_type: Optional[str] = None) -> List[Dict[str, Any]]:
        models = self._models.values()
        if model_type:
            models = [m for m in models if m.model_type == model_type]
        return [m.get_stats() for m in models]

    def select_model(self, model_type: str) -> Optional[ModelVersion]:
        """Select the best active model for a given type using weighted random selection."""
        candidates = [m for m in self._models.values()
                       if m.model_type == model_type and m.is_active]
        if not candidates:
            return None
        # Check for active A/B experiment
        for exp in self._experiments.values():
            if exp.is_active:
                model_id = exp.route_request()
                model = self._models.get(model_id)
                if model and model.model_type == model_type:
                    return model
        # Weighted random selection
        total_weight = sum(c.weight for c in candidates)
        r = random.random() * total_weight
        cumulative = 0
        for c in candidates:
            cumulative += c.weight
            if r <= cumulative:
                return c
        return candidates[0]

    def create_experiment(self, name: str, model_a_id: str, model_b_id: str,
                           traffic_split: float = 0.5) -> Dict[str, Any]:
        """Create an A/B experiment between two models."""
        if model_a_id not in self._models or model_b_id not in self._models:
            return {"status": "error", "message": "One or both model IDs not found"}
        exp_id = f"exp-{str(uuid.uuid4())[:8]}"
        exp = ABExperiment(exp_id, name, model_a_id, model_b_id, traffic_split)
        self._experiments[exp_id] = exp
        logger.info("A/B experiment created", id=exp_id, a=model_a_id, b=model_b_id)
        return {"status": "created", "experiment_id": exp_id}

    def stop_experiment(self, experiment_id: str) -> Dict[str, Any]:
        exp = self._experiments.get(experiment_id)
        if not exp:
            return {"status": "not_found"}
        exp.is_active = False
        return {"status": "stopped", **exp.get_summary()}

    def list_experiments(self) -> List[Dict[str, Any]]:
        return [exp.get_summary() for exp in self._experiments.values()]

    def predict_onnx(self, model_id: str, features: List[float]) -> Dict[str, Any]:
        """Run ONNX inference on a registered model."""
        model = self._models.get(model_id)
        if not model:
            return {"error": f"Model {model_id} not found"}
        if not model.onnx_runner:
            return {"error": f"Model {model_id} has no ONNX runtime"}
        start = time.time()
        result = model.onnx_runner.predict(features)
        latency_ms = (time.time() - start) * 1000
        success = "error" not in result
        model.record_prediction(latency_ms, success)
        result["latency_ms"] = round(latency_ms, 2)
        return result

    def get_onnx_info(self, model_id: str) -> Dict[str, Any]:
        """Return ONNX model metadata for a registered model."""
        model = self._models.get(model_id)
        if not model:
            return {"error": "Model not found"}
        if not model.onnx_runner:
            return {"error": "No ONNX runtime for this model"}
        return model.onnx_runner.get_info()

    def get_stats(self) -> Dict[str, Any]:
        onnx_count = sum(1 for m in self._models.values() if m.onnx_runner and m.onnx_runner._loaded)
        return {
            "total_models": len(self._models),
            "active_models": sum(1 for m in self._models.values() if m.is_active),
            "onnx_loaded": onnx_count,
            "total_experiments": len(self._experiments),
            "active_experiments": sum(1 for e in self._experiments.values() if e.is_active),
            "model_types": list(set(m.model_type for m in self._models.values())),
        }

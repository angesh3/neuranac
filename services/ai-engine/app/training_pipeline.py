"""
ONNX Training Pipeline for Endpoint Profiler.
Collects labeled endpoint data, trains a scikit-learn classifier,
and exports it as an ONNX model for low-latency inference.
"""
import os
import json
import time
import structlog
import numpy as np
from typing import Dict, List, Any, Optional

logger = structlog.get_logger()

MODEL_PATH = os.getenv("AI_MODEL_PATH", "/data/models")
TRAINING_DATA_PATH = os.getenv("AI_TRAINING_DATA", "/data/training")

DEVICE_TYPES = [
    "windows-pc", "macos", "linux-workstation", "iphone", "android",
    "ipad", "printer", "ip-phone", "camera", "iot-sensor",
    "smart-tv", "gaming-console", "server", "switch", "access-point",
    "ai-agent", "ai-gpu-node", "unknown"
]

DEVICE_TYPE_IDX = {dt: i for i, dt in enumerate(DEVICE_TYPES)}


class TrainingPipeline:
    """Manages training data collection and ONNX model export."""

    def __init__(self):
        self._samples: List[Dict[str, Any]] = []
        self._model_version = 0

    async def add_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """Add a labeled training sample. Expects: {mac_address, device_type, vendor, features...}"""
        device_type = sample.get("device_type", "unknown")
        if device_type not in DEVICE_TYPE_IDX:
            return {"status": "error", "message": f"Unknown device_type: {device_type}"}

        self._samples.append({
            "mac": sample.get("mac_address", ""),
            "device_type": device_type,
            "vendor": sample.get("vendor", "Unknown"),
            "hostname": sample.get("hostname", ""),
            "dns_queries": sample.get("dns_queries", []),
            "ports": sample.get("ports_used", []),
            "timestamp": time.time(),
        })
        return {"status": "ok", "total_samples": len(self._samples)}

    async def get_stats(self) -> Dict[str, Any]:
        """Return training dataset statistics."""
        by_type: Dict[str, int] = {}
        for s in self._samples:
            dt = s["device_type"]
            by_type[dt] = by_type.get(dt, 0) + 1
        return {
            "total_samples": len(self._samples),
            "by_device_type": by_type,
            "model_version": self._model_version,
            "min_samples_to_train": 50,
            "ready_to_train": len(self._samples) >= 50,
        }

    async def train_and_export(self) -> Dict[str, Any]:
        """Train a classifier on collected samples and export as ONNX."""
        if len(self._samples) < 50:
            return {"status": "error", "message": f"Need at least 50 samples, have {len(self._samples)}"}

        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score

            X, y = self._prepare_dataset()

            clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
            scores = cross_val_score(clf, X, y, cv=min(5, len(set(y))), scoring="accuracy")
            clf.fit(X, y)

            accuracy = float(np.mean(scores))
            logger.info("Training complete", accuracy=accuracy, samples=len(self._samples))

            # Export to ONNX
            onnx_path = self._export_onnx(clf, X.shape[1])

            self._model_version += 1
            return {
                "status": "ok",
                "accuracy": round(accuracy, 4),
                "samples_used": len(self._samples),
                "model_path": onnx_path,
                "model_version": self._model_version,
                "cross_val_scores": [round(s, 4) for s in scores.tolist()],
            }
        except Exception as e:
            logger.error("Training failed", error=str(e))
            return {"status": "error", "message": str(e)}

    def _prepare_dataset(self):
        """Convert samples to numpy arrays for training."""
        X_list = []
        y_list = []
        for s in self._samples:
            features = [0.0] * 50
            features[0] = hash(s.get("vendor", "")) % 1000 / 1000.0
            features[1] = len(s.get("dns_queries", [])) / 100.0
            ports = s.get("ports", [])
            features[2] = len(ports) / 50.0
            for i, p in enumerate(ports[:10]):
                features[3 + i] = p / 65535.0
            hostname = s.get("hostname", "").lower()
            features[13] = 1.0 if "print" in hostname else 0.0
            features[14] = 1.0 if "phone" in hostname else 0.0
            features[15] = 1.0 if "camera" in hostname else 0.0
            features[16] = 1.0 if "iphone" in hostname or "ipad" in hostname else 0.0
            features[17] = 1.0 if "android" in hostname else 0.0
            X_list.append(features)
            y_list.append(DEVICE_TYPE_IDX.get(s["device_type"], len(DEVICE_TYPES) - 1))
        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int64)

    def _export_onnx(self, clf, n_features: int) -> str:
        """Export trained sklearn model to ONNX format."""
        os.makedirs(MODEL_PATH, exist_ok=True)
        onnx_path = os.path.join(MODEL_PATH, "endpoint_profiler.onnx")
        try:
            from skl2onnx import convert_sklearn
            from skl2onnx.common.data_types import FloatTensorType
            initial_type = [("input", FloatTensorType([None, n_features]))]
            onnx_model = convert_sklearn(clf, initial_types=initial_type)
            with open(onnx_path, "wb") as f:
                f.write(onnx_model.SerializeToString())
            logger.info("ONNX model exported", path=onnx_path)
        except ImportError:
            # skl2onnx not available — save as joblib fallback
            import joblib
            fallback_path = os.path.join(MODEL_PATH, "endpoint_profiler.joblib")
            joblib.dump(clf, fallback_path)
            logger.warning("skl2onnx not available, saved as joblib", path=fallback_path)
            onnx_path = fallback_path
        return onnx_path

"""ML-based endpoint profiling using ONNX Runtime"""
import os
import numpy as np
import structlog

from app.oui_database import lookup_vendor, get_oui_count

logger = structlog.get_logger()

MODEL_PATH = os.getenv("AI_MODEL_PATH", "/data/models")

# Known device types for classification
DEVICE_TYPES = [
    "windows-pc", "macos", "linux-workstation", "iphone", "android",
    "ipad", "printer", "ip-phone", "camera", "iot-sensor",
    "smart-tv", "gaming-console", "server", "switch", "access-point",
    "ai-agent", "ai-gpu-node", "unknown"
]


class EndpointProfiler:
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.model_version = "rule-based-v1"

    async def load_model(self):
        """Load ONNX profiling model if available, else use rule-based"""
        onnx_path = os.path.join(MODEL_PATH, "endpoint_profiler.onnx")
        if os.path.exists(onnx_path):
            try:
                import onnxruntime as ort
                self.model = ort.InferenceSession(onnx_path)
                self.model_loaded = True
                self.model_version = "onnx-v1"
                logger.info("ONNX profiling model loaded", path=onnx_path)
            except Exception as e:
                logger.warning("Failed to load ONNX model, using rule-based", error=str(e))
                self.model_loaded = False
        else:
            logger.info("No ONNX model found, using rule-based profiling")
            self.model_loaded = False

    async def predict(self, request: dict) -> dict:
        """Profile an endpoint based on its attributes"""
        mac = request.get("mac_address", "")
        oui = mac[:8].upper() if len(mac) >= 8 else ""
        vendor = lookup_vendor(mac) if mac else request.get("oui_vendor", "Unknown")
        if vendor == "Unknown":
            vendor = request.get("oui_vendor", "Unknown")

        radius_attrs = request.get("radius_attributes", {})
        dhcp_attrs = request.get("dhcp_attributes", {})
        dns_queries = request.get("dns_queries", [])
        ports = request.get("ports_used", [])

        if self.model and self.model_loaded:
            return await self._predict_onnx(mac, vendor, radius_attrs, dhcp_attrs, dns_queries, ports)
        else:
            return self._predict_rules(mac, vendor, radius_attrs, dhcp_attrs, dns_queries, ports)

    async def _predict_onnx(self, mac, vendor, radius_attrs, dhcp_attrs, dns_queries, ports) -> dict:
        """ONNX model inference"""
        features = self._extract_features(vendor, radius_attrs, dhcp_attrs, dns_queries, ports)
        input_array = np.array([features], dtype=np.float32)
        result = self.model.run(None, {"input": input_array})
        probabilities = result[0][0]
        top_idx = int(np.argmax(probabilities))
        confidence = float(probabilities[top_idx])

        top_candidates = sorted(
            [(DEVICE_TYPES[i], float(probabilities[i])) for i in range(len(DEVICE_TYPES))],
            key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "device_type": DEVICE_TYPES[top_idx],
            "vendor": vendor,
            "os": self._guess_os(DEVICE_TYPES[top_idx]),
            "confidence": confidence,
            "top_candidates": [{"device_type": dt, "confidence": c} for dt, c in top_candidates],
            "model_version": self.model_version,
        }

    def _predict_rules(self, mac, vendor, radius_attrs, dhcp_attrs, dns_queries, ports) -> dict:
        """Rule-based profiling fallback"""
        device_type = "unknown"
        confidence = 0.5
        os_name = "unknown"

        vendor_lower = vendor.lower()
        hostname = dhcp_attrs.get("hostname", "").lower()
        dhcp_options = dhcp_attrs.get("options", [])

        # Vendor-based rules
        if vendor_lower in ("apple",):
            if any(q for q in dns_queries if "apple.com" in q):
                device_type, confidence, os_name = "iphone", 0.7, "iOS"
            else:
                device_type, confidence, os_name = "macos", 0.6, "macOS"
        elif vendor_lower in ("samsung", "google"):
            device_type, confidence, os_name = "android", 0.6, "Android"
        elif vendor_lower in ("vmware",):
            device_type, confidence, os_name = "server", 0.7, "Linux"
        elif vendor_lower in ("cisco",):
            if 5060 in ports or 5061 in ports:
                device_type, confidence = "ip-phone", 0.8
            else:
                device_type, confidence = "switch", 0.6
        elif vendor_lower in ("raspberry pi",):
            device_type, confidence, os_name = "iot-sensor", 0.7, "Linux"

        # Hostname-based rules
        if "print" in hostname or "hp" in hostname:
            device_type, confidence = "printer", 0.7
        elif "iphone" in hostname:
            device_type, confidence, os_name = "iphone", 0.8, "iOS"
        elif "android" in hostname:
            device_type, confidence, os_name = "android", 0.8, "Android"

        # Port-based rules
        if 9100 in ports or 631 in ports:
            device_type, confidence = "printer", 0.8
        if 554 in ports or 8554 in ports:
            device_type, confidence = "camera", 0.7

        # AI agent detection
        if any(p in ports for p in [8888, 11434, 5000]) or any("openai" in q for q in dns_queries):
            device_type, confidence = "ai-agent", 0.6

        return {
            "device_type": device_type,
            "vendor": vendor,
            "os": os_name,
            "confidence": confidence,
            "top_candidates": [{"device_type": device_type, "confidence": confidence}],
            "model_version": self.model_version,
        }

    def _extract_features(self, vendor, radius_attrs, dhcp_attrs, dns_queries, ports) -> list:
        """Extract numeric features for ONNX model input"""
        features = [0.0] * 50
        features[0] = hash(vendor) % 1000 / 1000.0
        features[1] = len(dns_queries) / 100.0
        features[2] = len(ports) / 50.0
        for i, p in enumerate(ports[:10]):
            features[3 + i] = p / 65535.0
        return features

    def _guess_os(self, device_type: str) -> str:
        os_map = {
            "windows-pc": "Windows", "macos": "macOS", "linux-workstation": "Linux",
            "iphone": "iOS", "android": "Android", "ipad": "iPadOS",
            "server": "Linux", "ai-agent": "Linux", "ai-gpu-node": "Linux",
        }
        return os_map.get(device_type, "unknown")

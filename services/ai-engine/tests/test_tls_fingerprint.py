"""Tests for TLSFingerprinter — JA3/JA4 analysis, custom signatures, stats."""
import pytest
from app.tls_fingerprint import TLSFingerprinter, KNOWN_JA3_SIGNATURES, JA4_PATTERNS


@pytest.fixture
def fp():
    return TLSFingerprinter()


class TestJA3Analysis:
    def test_known_openai_signature(self, fp):
        ja3 = "cd08e31494f9531f560d64c695473da9"
        result = fp.analyze_ja3(ja3, endpoint_mac="AA:BB:CC:DD:EE:FF")
        assert result["matched"] is True
        assert result["service"] == "openai"
        assert result["is_ai_service"] is True
        assert result["risk"] == "high"

    def test_known_anthropic_signature(self, fp):
        ja3 = "a0e9f5d64349fb13191bc781f81f42e1"
        result = fp.analyze_ja3(ja3)
        assert result["service"] == "anthropic"
        assert result["is_ai_service"] is True

    def test_known_browser_signature(self, fp):
        ja3 = "b4c3b2a1f5e4d3c2b1a0f5e4d3c2b1a0"
        result = fp.analyze_ja3(ja3)
        assert result["service"] == "chrome"
        assert result["is_ai_service"] is False
        assert result["risk"] == "none"

    def test_unknown_signature(self, fp):
        result = fp.analyze_ja3("0000000000000000000000000000000")
        assert result["matched"] is False
        assert result["service"] == "unknown"
        assert result["is_ai_service"] is False

    def test_detection_logged_for_ai_service(self, fp):
        fp.analyze_ja3("cd08e31494f9531f560d64c695473da9", endpoint_mac="AA:BB:CC:DD:EE:FF")
        detections = fp.get_detections()
        assert len(detections) == 1
        assert detections[0]["service"] == "openai"

    def test_no_detection_logged_for_browser(self, fp):
        fp.analyze_ja3("b4c3b2a1f5e4d3c2b1a0f5e4d3c2b1a0")
        assert len(fp.get_detections()) == 0


class TestJA4Analysis:
    def test_known_ja4_openai(self, fp):
        ja4 = "t13d1516h2_8daaf6152771_e5627efa2ab1"
        result = fp.analyze_ja4(ja4)
        assert result["matched"] is True
        assert result["service"] == "openai"

    def test_unknown_ja4(self, fp):
        result = fp.analyze_ja4("unknown_hash_value")
        assert result["matched"] is False


class TestComputeJA3:
    def test_compute_returns_md5_hex(self, fp):
        ja3 = fp.compute_ja3(771, [49195, 49199], [0, 23], [29, 23], [0])
        assert len(ja3) == 32  # MD5 hex
        assert all(c in "0123456789abcdef" for c in ja3)

    def test_same_input_same_hash(self, fp):
        a = fp.compute_ja3(771, [49195], [0], [29], [0])
        b = fp.compute_ja3(771, [49195], [0], [29], [0])
        assert a == b

    def test_different_input_different_hash(self, fp):
        a = fp.compute_ja3(771, [49195], [0], [29], [0])
        b = fp.compute_ja3(772, [49195], [0], [29], [0])
        assert a != b


class TestCustomSignatures:
    def test_add_custom_signature(self, fp):
        result = fp.add_custom_signature("deadbeef" * 4, "custom_ai", "My AI Service")
        assert result["status"] == "ok"
        assert result["total_custom"] == 1

    def test_custom_signature_detected(self, fp):
        custom_hash = "deadbeef" * 4
        fp.add_custom_signature(custom_hash, "custom_ai", "My AI Service", risk="high")
        result = fp.analyze_ja3(custom_hash)
        assert result["matched"] is True
        assert result["service"] == "custom_ai"

    def test_custom_overrides_builtin(self, fp):
        # Add custom with same hash as a known signature
        ja3 = "cd08e31494f9531f560d64c695473da9"
        fp.add_custom_signature(ja3, "overridden", "Overridden OpenAI")
        result = fp.analyze_ja3(ja3)
        assert result["service"] == "overridden"


class TestStats:
    def test_stats_initial(self, fp):
        stats = fp.get_stats()
        assert stats["total_detections"] == 0
        assert stats["known_signatures"] == len(KNOWN_JA3_SIGNATURES)
        assert stats["ja4_patterns"] == len(JA4_PATTERNS)

    def test_stats_after_detections(self, fp):
        fp.analyze_ja3("cd08e31494f9531f560d64c695473da9")
        fp.analyze_ja3("a0e9f5d64349fb13191bc781f81f42e1")
        stats = fp.get_stats()
        assert stats["total_detections"] == 2
        assert "openai" in stats["by_service"]
        assert "anthropic" in stats["by_service"]

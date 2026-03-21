"""Tests for TrainingPipeline — sample collection, stats, dataset preparation."""
import pytest
from app.training_pipeline import TrainingPipeline, DEVICE_TYPES, DEVICE_TYPE_IDX


@pytest.fixture
def pipeline():
    return TrainingPipeline()


class TestDeviceTypes:
    def test_device_types_count(self):
        assert len(DEVICE_TYPES) >= 18

    def test_device_type_index_mapping(self):
        for dt in DEVICE_TYPES:
            assert dt in DEVICE_TYPE_IDX


class TestAddSample:
    @pytest.mark.asyncio
    async def test_add_valid_sample(self, pipeline):
        result = await pipeline.add_sample({
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "device_type": "windows-pc",
            "vendor": "Dell",
            "hostname": "DESKTOP-ABC",
        })
        assert result["status"] == "ok"
        assert result["total_samples"] == 1

    @pytest.mark.asyncio
    async def test_add_unknown_device_type(self, pipeline):
        result = await pipeline.add_sample({
            "device_type": "totally-invalid-type",
        })
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_add_multiple_samples(self, pipeline):
        for i in range(5):
            await pipeline.add_sample({
                "mac_address": f"AA:BB:CC:DD:EE:{i:02X}",
                "device_type": "windows-pc",
            })
        stats = await pipeline.get_stats()
        assert stats["total_samples"] == 5


class TestGetStats:
    @pytest.mark.asyncio
    async def test_empty_stats(self, pipeline):
        stats = await pipeline.get_stats()
        assert stats["total_samples"] == 0
        assert stats["ready_to_train"] is False
        assert stats["min_samples_to_train"] == 50

    @pytest.mark.asyncio
    async def test_stats_by_device_type(self, pipeline):
        for _ in range(3):
            await pipeline.add_sample({"device_type": "windows-pc"})
        for _ in range(2):
            await pipeline.add_sample({"device_type": "iphone"})
        stats = await pipeline.get_stats()
        assert stats["by_device_type"]["windows-pc"] == 3
        assert stats["by_device_type"]["iphone"] == 2


class TestPrepareDataset:
    def test_prepare_dataset(self, pipeline):
        pipeline._samples = [
            {"device_type": "windows-pc", "vendor": "Dell", "hostname": "DESKTOP-1",
             "dns_queries": ["example.com"], "ports": [80, 443]},
            {"device_type": "printer", "vendor": "HP", "hostname": "HP-Printer-1",
             "dns_queries": [], "ports": [9100, 631]},
        ]
        X, y = pipeline._prepare_dataset()
        assert X.shape == (2, 50)
        assert y.shape == (2,)
        assert y[0] == DEVICE_TYPE_IDX["windows-pc"]
        assert y[1] == DEVICE_TYPE_IDX["printer"]

    def test_printer_hostname_feature(self, pipeline):
        pipeline._samples = [
            {"device_type": "printer", "vendor": "HP", "hostname": "HP-Printer-1",
             "dns_queries": [], "ports": []},
        ]
        X, _ = pipeline._prepare_dataset()
        # Feature 13 is printer hostname indicator
        assert X[0][13] == 1.0


class TestTrainAndExport:
    @pytest.mark.asyncio
    async def test_insufficient_samples(self, pipeline):
        for i in range(10):
            await pipeline.add_sample({"device_type": "windows-pc"})
        result = await pipeline.train_and_export()
        assert result["status"] == "error"
        assert "50 samples" in result["message"]

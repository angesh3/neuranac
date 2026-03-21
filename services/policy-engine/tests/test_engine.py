"""Tests for Policy Engine evaluator"""
import pytest
import asyncio
from app.engine import PolicyEvaluator


class TestPolicyEvaluator:
    def setup_method(self):
        self.evaluator = PolicyEvaluator.__new__(PolicyEvaluator)
        self.evaluator.policies = []
        self.evaluator.rules = {}
        self.evaluator.profiles = {}

    def test_compare_equals(self):
        assert self.evaluator._compare("admin", "equals", "admin") is True
        assert self.evaluator._compare("admin", "equals", "user") is False

    def test_compare_not_equals(self):
        assert self.evaluator._compare("admin", "not_equals", "user") is True
        assert self.evaluator._compare("admin", "not_equals", "admin") is False

    def test_compare_contains(self):
        assert self.evaluator._compare("employees_group", "contains", "employee") is True
        assert self.evaluator._compare("admins", "contains", "employee") is False

    def test_compare_starts_with(self):
        assert self.evaluator._compare("DESKTOP-ABC", "starts_with", "DESKTOP-") is True
        assert self.evaluator._compare("LAPTOP-XYZ", "starts_with", "DESKTOP-") is False

    def test_compare_ends_with(self):
        assert self.evaluator._compare("user@corp.com", "ends_with", "@corp.com") is True
        assert self.evaluator._compare("user@gmail.com", "ends_with", "@corp.com") is False

    def test_compare_in(self):
        assert self.evaluator._compare("admin", "in", "admin,user,guest") is True
        assert self.evaluator._compare("hacker", "in", "admin,user,guest") is False

    def test_compare_not_in(self):
        assert self.evaluator._compare("hacker", "not_in", "admin,user,guest") is True
        assert self.evaluator._compare("admin", "not_in", "admin,user,guest") is False

    def test_compare_matches(self):
        assert self.evaluator._compare("DESKTOP-ABC123", "matches", "^DESKTOP-.*") is True
        assert self.evaluator._compare("LAPTOP-XYZ", "matches", "^DESKTOP-.*") is False

    def test_compare_greater_than(self):
        assert self.evaluator._compare("75", "greater_than", "50") is True
        assert self.evaluator._compare("25", "greater_than", "50") is False

    def test_compare_less_than(self):
        assert self.evaluator._compare("25", "less_than", "50") is True
        assert self.evaluator._compare("75", "less_than", "50") is False

    def test_compare_between(self):
        assert self.evaluator._compare("50", "between", "30,70") is True
        assert self.evaluator._compare("80", "between", "30,70") is False
        assert self.evaluator._compare("30", "between", "30,70") is True  # inclusive

    def test_compare_is_true(self):
        assert self.evaluator._compare("true", "is_true", "") is True
        assert self.evaluator._compare("1", "is_true", "") is True
        assert self.evaluator._compare("yes", "is_true", "") is True
        assert self.evaluator._compare("false", "is_true", "") is False

    def test_compare_is_false(self):
        assert self.evaluator._compare("false", "is_false", "") is True
        assert self.evaluator._compare("0", "is_false", "") is True
        assert self.evaluator._compare("true", "is_false", "") is False

    def test_compare_invalid_operator(self):
        assert self.evaluator._compare("foo", "unknown_op", "bar") is False

    def test_compare_case_insensitive(self):
        assert self.evaluator._compare("Admin", "equals", "admin") is True
        assert self.evaluator._compare("ADMIN", "contains", "admin") is True


class TestPolicyEvaluatorSiteContext:
    def test_default_site_context(self):
        evaluator = PolicyEvaluator()
        assert evaluator.site_id == ""
        assert evaluator.site_type == "onprem"
        assert evaluator.deployment_mode == "standalone"

    def test_custom_site_context(self):
        evaluator = PolicyEvaluator(
            site_id="aaaa-bbbb-cccc",
            site_type="cloud",
            deployment_mode="hybrid",
        )
        assert evaluator.site_id == "aaaa-bbbb-cccc"
        assert evaluator.site_type == "cloud"
        assert evaluator.deployment_mode == "hybrid"

    def test_hybrid_onprem_site(self):
        evaluator = PolicyEvaluator(
            site_id="00000000-0000-0000-0000-000000000001",
            site_type="onprem",
            deployment_mode="hybrid",
        )
        assert evaluator.site_type == "onprem"
        assert evaluator.deployment_mode == "hybrid"

    def test_standalone_cloud_site(self):
        evaluator = PolicyEvaluator(
            site_id="00000000-0000-0000-0000-000000000002",
            site_type="cloud",
            deployment_mode="standalone",
        )
        assert evaluator.site_type == "cloud"
        assert evaluator.deployment_mode == "standalone"

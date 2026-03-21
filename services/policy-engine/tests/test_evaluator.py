"""Tests for Policy Engine — evaluate, condition matching, attribute resolution, authorization"""
import pytest
from app.engine import PolicyEvaluator


class TestResolveAttribute:
    def setup_method(self):
        self.evaluator = PolicyEvaluator.__new__(PolicyEvaluator)
        self.evaluator.policy_sets = []
        self.evaluator.rules = []
        self.evaluator.auth_profiles = {}

    def test_simple_key(self):
        assert self.evaluator._resolve_attribute("username", {"username": "alice"}) == "alice"

    def test_dotted_path(self):
        req = {"identity": {"groups": "employees"}}
        assert self.evaluator._resolve_attribute("identity.groups", req) == "employees"

    def test_deep_dotted_path(self):
        req = {"network": {"device": {"vendor": "Cisco"}}}
        assert self.evaluator._resolve_attribute("network.device.vendor", req) == "Cisco"

    def test_missing_key(self):
        assert self.evaluator._resolve_attribute("missing", {"username": "alice"}) is None

    def test_missing_nested(self):
        assert self.evaluator._resolve_attribute("a.b.c", {"a": {"x": 1}}) is None

    def test_non_dict_intermediate(self):
        assert self.evaluator._resolve_attribute("a.b", {"a": 42}) is None

    def test_numeric_value_converted(self):
        assert self.evaluator._resolve_attribute("score", {"score": 75}) == "75"


class TestMatchConditions:
    def setup_method(self):
        self.evaluator = PolicyEvaluator.__new__(PolicyEvaluator)
        self.evaluator.policy_sets = []
        self.evaluator.rules = []
        self.evaluator.auth_profiles = {}

    def test_empty_conditions(self):
        assert self.evaluator._match_conditions([], {"username": "alice"}) is True

    def test_single_match(self):
        conds = [{"attribute": "username", "operator": "equals", "value": "alice"}]
        assert self.evaluator._match_conditions(conds, {"username": "alice"}) is True

    def test_single_no_match(self):
        conds = [{"attribute": "username", "operator": "equals", "value": "bob"}]
        assert self.evaluator._match_conditions(conds, {"username": "alice"}) is False

    def test_multiple_all_match(self):
        conds = [
            {"attribute": "username", "operator": "equals", "value": "alice"},
            {"attribute": "role", "operator": "equals", "value": "admin"},
        ]
        assert self.evaluator._match_conditions(conds, {"username": "alice", "role": "admin"}) is True

    def test_multiple_partial_match(self):
        conds = [
            {"attribute": "username", "operator": "equals", "value": "alice"},
            {"attribute": "role", "operator": "equals", "value": "admin"},
        ]
        assert self.evaluator._match_conditions(conds, {"username": "alice", "role": "user"}) is False

    def test_missing_attribute_fails(self):
        conds = [{"attribute": "nonexistent", "operator": "equals", "value": "x"}]
        assert self.evaluator._match_conditions(conds, {"username": "alice"}) is False

    def test_dotted_attribute(self):
        conds = [{"attribute": "identity.groups", "operator": "contains", "value": "employee"}]
        assert self.evaluator._match_conditions(conds, {"identity": {"groups": "employees"}}) is True


class TestRuleMatchesTenant:
    def setup_method(self):
        self.evaluator = PolicyEvaluator.__new__(PolicyEvaluator)
        self.evaluator.rules = []
        self.evaluator.auth_profiles = {}
        self.evaluator.policy_sets = [
            {"id": "ps-1", "tenant_id": "t-100", "name": "Corp", "priority": 1},
            {"id": "ps-2", "tenant_id": "t-200", "name": "Guest", "priority": 2},
        ]

    def test_matching_tenant(self):
        rule = {"policy_set_id": "ps-1"}
        assert self.evaluator._rule_matches_tenant(rule, "t-100") is True

    def test_wrong_tenant(self):
        rule = {"policy_set_id": "ps-1"}
        assert self.evaluator._rule_matches_tenant(rule, "t-200") is False

    def test_empty_tenant_matches_all(self):
        rule = {"policy_set_id": "ps-1"}
        assert self.evaluator._rule_matches_tenant(rule, "") is True

    def test_unknown_policy_set(self):
        rule = {"policy_set_id": "ps-999"}
        assert self.evaluator._rule_matches_tenant(rule, "t-100") is False


class TestBuildAuthorization:
    def setup_method(self):
        self.evaluator = PolicyEvaluator.__new__(PolicyEvaluator)

    def test_empty_profile(self):
        assert self.evaluator._build_authorization({}) == {}

    def test_full_profile(self):
        profile = {
            "vlan_id": 100,
            "vlan_name": "corporate",
            "sgt_value": 10,
            "dacl_id": "dacl-1",
            "ipsk": None,
            "coa_action": "reauthenticate",
            "group_policy": "FullAccess",
            "voice_domain": True,
            "redirect_url": None,
            "session_timeout": 3600,
            "bandwidth_limit_mbps": 100,
            "destination_whitelist": ["10.0.0.0/8"],
            "vendor_attributes": {"cisco-av-pair": "test"},
        }
        result = self.evaluator._build_authorization(profile)
        assert result["vlan_id"] == 100
        assert result["sgt_value"] == 10
        assert result["voice_domain"] is True
        assert result["session_timeout"] == 3600
        assert result["vendor_attributes"] == {"cisco-av-pair": "test"}


class TestEvaluate:
    def setup_method(self):
        self.evaluator = PolicyEvaluator.__new__(PolicyEvaluator)
        self.evaluator.site_id = ""
        self.evaluator.site_type = "onprem"
        self.evaluator.deployment_mode = "standalone"
        self.evaluator.policy_sets = [
            {"id": "ps-1", "tenant_id": "t-1", "name": "Corp", "priority": 1},
        ]
        self.evaluator.rules = [
            {
                "id": "r-1", "policy_set_id": "ps-1", "name": "Allow Admins",
                "priority": 1, "action": "permit",
                "conditions": [{"attribute": "role", "operator": "equals", "value": "admin"}],
                "auth_profile_id": "ap-1",
            },
            {
                "id": "r-2", "policy_set_id": "ps-1", "name": "Deny Guests",
                "priority": 2, "action": "deny",
                "conditions": [{"attribute": "role", "operator": "equals", "value": "guest"}],
                "auth_profile_id": "ap-2",
            },
        ]
        self.evaluator.auth_profiles = {
            "ap-1": {"vlan_id": 10, "vlan_name": "admin"},
            "ap-2": {"vlan_id": 999, "vlan_name": "quarantine"},
        }

    @pytest.mark.asyncio
    async def test_match_first_rule(self):
        result = await self.evaluator.evaluate({"tenant_id": "t-1", "role": "admin"})
        assert result["decision"]["type"] == "permit"
        assert result["matched_rule_name"] == "Allow Admins"
        assert result["authorization"]["vlan_id"] == 10
        assert result["evaluation_time_us"] >= 0

    @pytest.mark.asyncio
    async def test_match_second_rule(self):
        result = await self.evaluator.evaluate({"tenant_id": "t-1", "role": "guest"})
        assert result["decision"]["type"] == "deny"
        assert result["matched_rule_name"] == "Deny Guests"

    @pytest.mark.asyncio
    async def test_default_deny(self):
        result = await self.evaluator.evaluate({"tenant_id": "t-1", "role": "unknown"})
        assert result["decision"]["type"] == "deny"
        assert result["matched_rule_id"] is None

    @pytest.mark.asyncio
    async def test_wrong_tenant_default_deny(self):
        result = await self.evaluator.evaluate({"tenant_id": "t-999", "role": "admin"})
        assert result["decision"]["type"] == "deny"
        assert result["matched_rule_id"] is None

    @pytest.mark.asyncio
    async def test_empty_tenant_matches(self):
        result = await self.evaluator.evaluate({"tenant_id": "", "role": "admin"})
        assert result["decision"]["type"] == "permit"

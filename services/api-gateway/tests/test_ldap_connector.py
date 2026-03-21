"""Tests for LDAP/AD identity source connector."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.ldap_connector import (
    LDAPConfig,
    LDAPConnector,
    LDAPUser,
)


class TestLDAPConfig:
    def test_from_dict_defaults(self):
        cfg = LDAPConfig.from_dict({
            "server": "ldap://dc.corp.local",
            "bind_dn": "CN=svc,DC=corp,DC=local",
            "bind_password": "secret",
            "base_dn": "DC=corp,DC=local",
        })
        assert cfg.server_urls == ["ldap://dc.corp.local"]
        assert cfg.bind_dn == "CN=svc,DC=corp,DC=local"
        assert cfg.base_dn == "DC=corp,DC=local"
        assert cfg.use_ssl is False  # ldap:// not ldaps://
        assert cfg.pool_size == 5
        assert cfg.page_size == 500
        assert cfg.auth_method == "SIMPLE"

    def test_from_dict_ldaps(self):
        cfg = LDAPConfig.from_dict({
            "server": "ldaps://dc.corp.local:636",
            "bind_dn": "CN=svc,DC=corp,DC=local",
            "bind_password": "secret",
            "base_dn": "DC=corp,DC=local",
        })
        assert cfg.use_ssl is True

    def test_from_dict_multiple_servers(self):
        cfg = LDAPConfig.from_dict({
            "server_urls": ["ldaps://dc1.corp.local", "ldaps://dc2.corp.local"],
            "bind_dn": "CN=svc,DC=corp,DC=local",
            "bind_password": "secret",
            "base_dn": "DC=corp,DC=local",
        })
        assert len(cfg.server_urls) == 2

    def test_from_dict_custom_filters(self):
        cfg = LDAPConfig.from_dict({
            "server": "ldap://localhost",
            "bind_dn": "",
            "bind_password": "",
            "base_dn": "DC=test",
            "user_filter": "(uid={username})",
            "page_size": 100,
            "auth_method": "NTLM",
        })
        assert cfg.user_filter == "(uid={username})"
        assert cfg.page_size == 100
        assert cfg.auth_method == "NTLM"


class TestLDAPUser:
    def test_defaults(self):
        user = LDAPUser(dn="CN=test,DC=corp", username="test")
        assert user.email == ""
        assert user.display_name == ""
        assert user.groups == []
        assert user.attributes == {}
        assert user.disabled is False

    def test_full_user(self):
        user = LDAPUser(
            dn="CN=John,OU=Users,DC=corp",
            username="john",
            email="john@corp.local",
            display_name="John Doe",
            groups=["CN=Admins,DC=corp", "CN=Users,DC=corp"],
            disabled=False,
        )
        assert user.username == "john"
        assert len(user.groups) == 2


class TestLDAPConnector:
    def test_init(self):
        cfg = LDAPConfig(
            server_urls=["ldap://localhost"],
            bind_dn="cn=admin",
            bind_password="secret",
            base_dn="dc=test",
        )
        connector = LDAPConnector(cfg)
        assert connector._cfg == cfg
        assert connector._server_pool is None
        assert connector._bind_conn is None

    @patch("app.services.ldap_connector.Connection")
    @patch("app.services.ldap_connector.Server")
    @patch("app.services.ldap_connector.ServerPool")
    def test_connect_sync(self, mock_pool, mock_server, mock_conn):
        cfg = LDAPConfig(
            server_urls=["ldap://localhost:389"],
            bind_dn="cn=admin,dc=test",
            bind_password="secret",
            base_dn="dc=test",
            use_ssl=False,
            use_starttls=False,
        )
        connector = LDAPConnector(cfg)
        result = connector._connect_sync()
        assert result is True
        mock_server.assert_called_once()
        mock_pool.assert_called_once()
        mock_conn.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        cfg = LDAPConfig(
            server_urls=["ldap://nonexistent:389"],
            bind_dn="cn=admin",
            bind_password="secret",
            base_dn="dc=test",
            connect_timeout=1,
        )
        connector = LDAPConnector(cfg)
        result = await connector.test_connection()
        assert result["status"] in ("connection_failed", "bind_failed", "error")

    @pytest.mark.asyncio
    async def test_disconnect_no_conn(self):
        cfg = LDAPConfig(
            server_urls=["ldap://localhost"],
            bind_dn="",
            bind_password="",
            base_dn="",
        )
        connector = LDAPConnector(cfg)
        # Should not raise even with no connection
        await connector.disconnect()

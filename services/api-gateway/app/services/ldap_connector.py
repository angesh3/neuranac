"""LDAP/Active Directory identity source connector.

Provides connection pooling, bind authentication, user/group search,
and group membership resolution for AD and LDAP identity sources.
"""

import asyncio
import logging
import ssl
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import ldap3
from ldap3 import ALL, NTLM, SIMPLE, SUBTREE, Connection, Server, ServerPool, Tls
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPException,
    LDAPSocketOpenError,
)

logger = logging.getLogger("neuranac.ldap_connector")


@dataclass
class LDAPUser:
    """Represents a user retrieved from LDAP/AD."""
    dn: str
    username: str
    email: str = ""
    display_name: str = ""
    groups: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    disabled: bool = False


@dataclass
class LDAPConfig:
    """Configuration for an LDAP/AD connection."""
    server_urls: List[str]  # e.g. ["ldaps://dc1.corp.local:636", "ldaps://dc2.corp.local:636"]
    bind_dn: str            # e.g. "CN=svc-neuranac,OU=Service Accounts,DC=corp,DC=local"
    bind_password: str
    base_dn: str            # e.g. "DC=corp,DC=local"
    user_search_base: str = ""  # defaults to base_dn
    group_search_base: str = "" # defaults to base_dn
    user_filter: str = "(&(objectClass=user)(sAMAccountName={username}))"
    group_filter: str = "(objectClass=group)"
    user_attributes: List[str] = field(default_factory=lambda: [
        "cn", "sAMAccountName", "mail", "displayName",
        "memberOf", "userAccountControl", "distinguishedName",
    ])
    group_attributes: List[str] = field(default_factory=lambda: [
        "cn", "distinguishedName", "member",
    ])
    use_ssl: bool = True
    use_starttls: bool = False
    verify_ssl: bool = True
    connect_timeout: int = 10
    receive_timeout: int = 30
    pool_size: int = 5
    auth_method: str = "SIMPLE"  # SIMPLE or NTLM
    page_size: int = 500
    referral_following: bool = False

    @classmethod
    def from_dict(cls, cfg: dict) -> "LDAPConfig":
        """Build LDAPConfig from an identity source config dict."""
        server_url = cfg.get("server", "ldap://localhost:389")
        urls = cfg.get("server_urls", [server_url] if isinstance(server_url, str) else server_url)
        return cls(
            server_urls=urls,
            bind_dn=cfg.get("bind_dn", ""),
            bind_password=cfg.get("bind_password", ""),
            base_dn=cfg.get("base_dn", ""),
            user_search_base=cfg.get("user_search_base", cfg.get("base_dn", "")),
            group_search_base=cfg.get("group_search_base", cfg.get("base_dn", "")),
            user_filter=cfg.get("user_filter", "(&(objectClass=user)(sAMAccountName={username}))"),
            group_filter=cfg.get("group_filter", "(objectClass=group)"),
            use_ssl=cfg.get("use_ssl", server_url.startswith("ldaps")),
            use_starttls=cfg.get("use_starttls", False),
            verify_ssl=cfg.get("verify_ssl", True),
            connect_timeout=cfg.get("connect_timeout", 10),
            receive_timeout=cfg.get("receive_timeout", 30),
            pool_size=cfg.get("pool_size", 5),
            auth_method=cfg.get("auth_method", "SIMPLE"),
            page_size=cfg.get("page_size", 500),
        )


class LDAPConnector:
    """LDAP/AD connector with connection pooling, authentication, and search."""

    def __init__(self, config: LDAPConfig):
        self._cfg = config
        self._server_pool: Optional[ServerPool] = None
        self._bind_conn: Optional[Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Establish connection pool to LDAP server(s)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._connect_sync)

    def _connect_sync(self) -> bool:
        tls_config = None
        if self._cfg.use_ssl or self._cfg.use_starttls:
            validate = ssl.CERT_REQUIRED if self._cfg.verify_ssl else ssl.CERT_NONE
            tls_config = Tls(validate=validate, version=ssl.PROTOCOL_TLSv1_2)

        servers = []
        for url in self._cfg.server_urls:
            use_ssl = url.startswith("ldaps://")
            srv = Server(
                url,
                use_ssl=use_ssl,
                tls=tls_config,
                get_info=ALL,
                connect_timeout=self._cfg.connect_timeout,
            )
            servers.append(srv)

        self._server_pool = ServerPool(servers, pool_strategy=ldap3.ROUND_ROBIN, active=True)

        auth_method = NTLM if self._cfg.auth_method == "NTLM" else SIMPLE
        self._bind_conn = Connection(
            self._server_pool,
            user=self._cfg.bind_dn,
            password=self._cfg.bind_password,
            authentication=auth_method,
            auto_bind=True,
            receive_timeout=self._cfg.receive_timeout,
            auto_referrals=self._cfg.referral_following,
        )
        logger.info("LDAP bind successful to %s", self._cfg.server_urls)
        return True

    async def disconnect(self):
        """Close all connections."""
        if self._bind_conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._bind_conn.unbind)
            self._bind_conn = None

    async def test_connection(self) -> Dict[str, Any]:
        """Test LDAP connectivity and return server info."""
        try:
            ok = await self.connect()
            if not ok:
                return {"status": "connection_failed"}

            info = {}
            if self._bind_conn and self._bind_conn.server and self._bind_conn.server.info:
                si = self._bind_conn.server.info
                info["naming_contexts"] = list(si.naming_contexts) if si.naming_contexts else []
                info["supported_ldap_versions"] = list(si.supported_ldap_versions) if si.supported_ldap_versions else []

            await self.disconnect()
            return {"status": "connection_ok", "server_info": info}
        except LDAPSocketOpenError as e:
            return {"status": "connection_failed", "error": f"Socket error: {e}"}
        except LDAPBindError as e:
            return {"status": "bind_failed", "error": f"Bind error: {e}"}
        except LDAPException as e:
            return {"status": "error", "error": str(e)}

    async def authenticate_user(self, username: str, password: str) -> Optional[LDAPUser]:
        """Authenticate a user by performing an LDAP bind with their credentials.

        1. Search for the user DN using the service account bind
        2. Attempt a bind with the user's DN and password
        3. Return LDAPUser with group memberships on success
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._authenticate_sync, username, password)

    def _authenticate_sync(self, username: str, password: str) -> Optional[LDAPUser]:
        if not self._bind_conn or not self._bind_conn.bound:
            self._connect_sync()

        # Step 1: Find user DN
        search_base = self._cfg.user_search_base or self._cfg.base_dn
        search_filter = self._cfg.user_filter.replace("{username}", ldap3.utils.conv.escape_filter_chars(username))

        self._bind_conn.search(
            search_base,
            search_filter,
            search_scope=SUBTREE,
            attributes=self._cfg.user_attributes,
            size_limit=1,
        )

        if not self._bind_conn.entries:
            logger.warning("LDAP user not found: %s", username)
            return None

        entry = self._bind_conn.entries[0]
        user_dn = entry.entry_dn

        # Step 2: Bind with user credentials to verify password
        try:
            user_conn = Connection(
                self._server_pool,
                user=user_dn,
                password=password,
                authentication=SIMPLE,
                auto_bind=True,
                receive_timeout=self._cfg.receive_timeout,
            )
            user_conn.unbind()
        except LDAPBindError:
            logger.warning("LDAP bind failed for user: %s", username)
            return None
        except LDAPException as e:
            logger.error("LDAP error during user bind: %s", e)
            return None

        # Step 3: Build user object
        attrs = {str(k): str(v) for k, v in entry.entry_attributes_as_dict.items() if v}
        groups = []
        member_of = entry.entry_attributes_as_dict.get("memberOf", [])
        for g in member_of:
            groups.append(str(g))

        # Check userAccountControl for disabled flag (AD-specific, bit 1 = ACCOUNTDISABLE)
        disabled = False
        uac = entry.entry_attributes_as_dict.get("userAccountControl", [])
        if uac:
            try:
                uac_val = int(str(uac[0]))
                disabled = bool(uac_val & 0x02)
            except (ValueError, IndexError):
                pass

        return LDAPUser(
            dn=user_dn,
            username=str(entry.entry_attributes_as_dict.get("sAMAccountName", [username])[0]),
            email=str(entry.entry_attributes_as_dict.get("mail", [""])[0]),
            display_name=str(entry.entry_attributes_as_dict.get("displayName", [""])[0]),
            groups=groups,
            attributes=attrs,
            disabled=disabled,
        )

    async def search_users(
        self, search_filter: str = "(objectClass=user)", page_size: int = 0
    ) -> List[LDAPUser]:
        """Search for users with paged results."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._search_users_sync, search_filter, page_size)

    def _search_users_sync(self, search_filter: str, page_size: int) -> List[LDAPUser]:
        if not self._bind_conn or not self._bind_conn.bound:
            self._connect_sync()

        search_base = self._cfg.user_search_base or self._cfg.base_dn
        ps = page_size or self._cfg.page_size

        self._bind_conn.search(
            search_base,
            search_filter,
            search_scope=SUBTREE,
            attributes=self._cfg.user_attributes,
            paged_size=ps,
        )

        users = []
        for entry in self._bind_conn.entries:
            attrs_dict = entry.entry_attributes_as_dict
            groups = [str(g) for g in attrs_dict.get("memberOf", [])]
            users.append(LDAPUser(
                dn=entry.entry_dn,
                username=str(attrs_dict.get("sAMAccountName", [""])[0]),
                email=str(attrs_dict.get("mail", [""])[0]),
                display_name=str(attrs_dict.get("displayName", [""])[0]),
                groups=groups,
            ))

        # Handle paged results cookie
        cookie = self._bind_conn.result.get("controls", {}).get("1.2.840.113556.1.4.319", {}).get("value", {}).get("cookie")
        while cookie:
            self._bind_conn.search(
                search_base,
                search_filter,
                search_scope=SUBTREE,
                attributes=self._cfg.user_attributes,
                paged_size=ps,
                paged_cookie=cookie,
            )
            for entry in self._bind_conn.entries:
                attrs_dict = entry.entry_attributes_as_dict
                groups = [str(g) for g in attrs_dict.get("memberOf", [])]
                users.append(LDAPUser(
                    dn=entry.entry_dn,
                    username=str(attrs_dict.get("sAMAccountName", [""])[0]),
                    email=str(attrs_dict.get("mail", [""])[0]),
                    display_name=str(attrs_dict.get("displayName", [""])[0]),
                    groups=groups,
                ))
            cookie = self._bind_conn.result.get("controls", {}).get("1.2.840.113556.1.4.319", {}).get("value", {}).get("cookie")

        return users

    async def get_user_groups(self, username: str) -> List[str]:
        """Get group DNs for a specific user."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_user_groups_sync, username)

    def _get_user_groups_sync(self, username: str) -> List[str]:
        if not self._bind_conn or not self._bind_conn.bound:
            self._connect_sync()

        search_base = self._cfg.user_search_base or self._cfg.base_dn
        search_filter = self._cfg.user_filter.replace("{username}", ldap3.utils.conv.escape_filter_chars(username))

        self._bind_conn.search(
            search_base,
            search_filter,
            search_scope=SUBTREE,
            attributes=["memberOf"],
            size_limit=1,
        )

        if not self._bind_conn.entries:
            return []

        return [str(g) for g in self._bind_conn.entries[0].entry_attributes_as_dict.get("memberOf", [])]

    async def resolve_nested_groups(self, group_dn: str, depth: int = 5) -> List[str]:
        """Resolve nested group memberships (AD supports LDAP_MATCHING_RULE_IN_CHAIN)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._resolve_nested_sync, group_dn, depth)

    def _resolve_nested_sync(self, group_dn: str, depth: int) -> List[str]:
        if not self._bind_conn or not self._bind_conn.bound:
            self._connect_sync()

        # AD-specific: use LDAP_MATCHING_RULE_IN_CHAIN (1.2.840.113556.1.4.1941)
        search_base = self._cfg.group_search_base or self._cfg.base_dn
        nested_filter = f"(memberOf:1.2.840.113556.1.4.1941:={ldap3.utils.conv.escape_filter_chars(group_dn)})"

        self._bind_conn.search(
            search_base,
            nested_filter,
            search_scope=SUBTREE,
            attributes=["distinguishedName"],
            size_limit=1000,
        )

        return [entry.entry_dn for entry in self._bind_conn.entries]


# Singleton registry of active LDAP connectors keyed by source_id
_connectors: Dict[str, LDAPConnector] = {}
_connectors_lock = asyncio.Lock()


async def get_connector(source_id: str, config_dict: dict) -> LDAPConnector:
    """Get or create an LDAP connector for the given identity source."""
    async with _connectors_lock:
        if source_id not in _connectors:
            cfg = LDAPConfig.from_dict(config_dict)
            connector = LDAPConnector(cfg)
            await connector.connect()
            _connectors[source_id] = connector
        return _connectors[source_id]


async def remove_connector(source_id: str):
    """Remove and disconnect an LDAP connector."""
    async with _connectors_lock:
        conn = _connectors.pop(source_id, None)
        if conn:
            await conn.disconnect()


async def shutdown_all():
    """Disconnect all LDAP connectors (called on app shutdown)."""
    async with _connectors_lock:
        for conn in _connectors.values():
            await conn.disconnect()
        _connectors.clear()

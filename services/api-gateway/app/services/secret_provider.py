"""Pluggable secret provider abstraction.

Supports multiple backends for secret retrieval:
  - env    : Read from environment variables (default, current behavior)
  - vault  : HashiCorp Vault via hvac library
  - aws    : AWS Secrets Manager via boto3

Set SECRET_PROVIDER=vault|aws to switch backends.
"""
import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("neuranac.secrets")


class SecretProvider(ABC):
    """Abstract interface for secret retrieval."""

    @abstractmethod
    async def get_secret(self, key: str, default: str = "") -> str:
        """Return the value for *key*, or *default* if not found."""

    async def get_secrets(self, keys: list[str]) -> dict[str, str]:
        """Batch-fetch multiple secrets."""
        return {k: await self.get_secret(k) for k in keys}

    async def close(self) -> None:
        """Release any resources held by the provider."""


class EnvSecretProvider(SecretProvider):
    """Read secrets from environment variables (default behaviour)."""

    async def get_secret(self, key: str, default: str = "") -> str:
        return os.getenv(key, default)


class VaultSecretProvider(SecretProvider):
    """Read secrets from HashiCorp Vault (KV v2).

    Required env vars:
        VAULT_ADDR          – e.g. https://vault.internal:8200
        VAULT_TOKEN         – auth token  (or use VAULT_ROLE_ID + VAULT_SECRET_ID for AppRole)
        VAULT_SECRET_PATH   – KV mount path, default "secret/data/neuranac"
    """

    def __init__(self) -> None:
        self._client = None
        self._cache: dict[str, str] = {}
        self._path = os.getenv("VAULT_SECRET_PATH", "secret/data/neuranac")

    async def _ensure_client(self):
        if self._client is not None:
            return
        try:
            import hvac  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError(
                "SECRET_PROVIDER=vault requires the 'hvac' package. "
                "Install it with: pip install hvac"
            )
        addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        token = os.getenv("VAULT_TOKEN", "")
        self._client = hvac.Client(url=addr, token=token)

        # AppRole auth fallback
        if not token:
            role_id = os.getenv("VAULT_ROLE_ID", "")
            secret_id = os.getenv("VAULT_SECRET_ID", "")
            if role_id and secret_id:
                self._client.auth.approle.login(role_id=role_id, secret_id=secret_id)
            else:
                raise RuntimeError(
                    "Vault: set VAULT_TOKEN or both VAULT_ROLE_ID and VAULT_SECRET_ID"
                )

        if not self._client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

        # Pre-fetch all secrets at the configured path
        try:
            resp = self._client.secrets.kv.v2.read_secret_version(path=self._path.split("/")[-1])
            self._cache = resp["data"]["data"]
            logger.info("Vault secrets loaded", extra={"path": self._path, "keys": len(self._cache)})
        except Exception as exc:
            logger.warning("Vault read failed, falling back to env vars", extra={"error": str(exc)})

    async def get_secret(self, key: str, default: str = "") -> str:
        await self._ensure_client()
        # Vault keys are typically lowercase; env vars are UPPER_CASE
        val = self._cache.get(key) or self._cache.get(key.lower())
        if val is not None:
            return str(val)
        # Fallback to environment
        return os.getenv(key, default)

    async def close(self) -> None:
        self._client = None
        self._cache.clear()


class AWSSecretsManagerProvider(SecretProvider):
    """Read secrets from AWS Secrets Manager.

    Required env vars:
        AWS_SECRET_NAME     – name or ARN of the secret (default "neuranac/config")
        AWS_REGION          – AWS region (default "us-east-1")
    AWS credentials are resolved via the standard boto3 chain (env, instance profile, etc.).
    """

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._loaded = False

    async def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError(
                "SECRET_PROVIDER=aws requires the 'boto3' package. "
                "Install it with: pip install boto3"
            )
        secret_name = os.getenv("AWS_SECRET_NAME", "neuranac/config")
        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("secretsmanager", region_name=region)
        try:
            resp = client.get_secret_value(SecretId=secret_name)
            secret_str = resp.get("SecretString", "{}")
            self._cache = json.loads(secret_str)
            logger.info("AWS Secrets Manager loaded", extra={"name": secret_name, "keys": len(self._cache)})
        except Exception as exc:
            logger.warning("AWS Secrets Manager read failed, falling back to env vars",
                           extra={"error": str(exc)})
        self._loaded = True

    async def get_secret(self, key: str, default: str = "") -> str:
        await self._ensure_loaded()
        val = self._cache.get(key) or self._cache.get(key.upper())
        if val is not None:
            return str(val)
        return os.getenv(key, default)

    async def close(self) -> None:
        self._cache.clear()
        self._loaded = False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_provider: Optional[SecretProvider] = None


def create_secret_provider() -> SecretProvider:
    """Create the secret provider based on SECRET_PROVIDER env var."""
    global _provider
    if _provider is not None:
        return _provider

    backend = os.getenv("SECRET_PROVIDER", "env").lower()
    if backend == "vault":
        _provider = VaultSecretProvider()
    elif backend == "aws":
        _provider = AWSSecretsManagerProvider()
    else:
        _provider = EnvSecretProvider()

    logger.info("Secret provider initialised", extra={"backend": backend})
    return _provider


def get_secret_provider() -> SecretProvider:
    """Return the current (or default) secret provider singleton."""
    global _provider
    if _provider is None:
        return create_secret_provider()
    return _provider

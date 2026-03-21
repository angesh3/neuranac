"""Application configuration loaded from environment variables"""
import os
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

_config_logger = logging.getLogger("neuranac.config")

# Module-level cache for auto-generated RSA keys to avoid regeneration
# between separate calls for private and public key.
_rsa_key_cache: dict = {}


class Settings(BaseSettings):
    # Secret management (env | vault | aws)
    secret_provider: str = "env"

    # App
    neuranac_env: str = "development"
    neuranac_node_id: str = "twin-a"
    neuranac_site_type: str = "onprem"
    neuranac_site_id: str = "00000000-0000-0000-0000-000000000001"

    # Deployment Mode (standalone = single site, hybrid = on-prem + cloud twin)
    deployment_mode: str = "standalone"
    neuranac_peer_api_url: str = ""
    bridge_url: str = ""  # URL to the NeuraNAC Bridge service
    federation_shared_secret: str = ""  # HMAC secret for inter-site federation auth

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "neuranac"
    postgres_user: str = "neuranac"
    postgres_password: str = "neuranac_dev_password"
    postgres_ssl_mode: str = "disable"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = "neuranac_dev_password"

    # NATS
    nats_url: str = "nats://localhost:4222"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_secret_key: str = "dev_secret_key_change_in_production_min32"

    # JWT
    jwt_secret_key: str = "dev_jwt_secret_key_change_in_production_min64chars_here"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "RS256"
    jwt_private_key_path: str = ""
    jwt_public_key_path: str = ""
    jwt_private_key: str = ""  # PEM content (alternative to file path)
    jwt_public_key: str = ""   # PEM content (alternative to file path)

    # AI Engine
    ai_engine_host: str = "localhost"
    ai_engine_port: int = 8081

    # Sync
    sync_peer_address: str = ""
    sync_grpc_port: int = 9090

    # TLS
    tls_cert_path: str = "/etc/neuranac/certs"
    tls_auto_generate: bool = True

    # Logging
    log_level: str = "info"
    log_format: str = "json"

    @property
    def jwt_signing_key(self) -> str:
        """Return the key used for signing JWTs (private key for RS256, secret for HS256)."""
        if self.jwt_algorithm == "RS256":
            return self._load_rsa_private_key()
        return self.jwt_secret_key

    @property
    def jwt_verify_key(self) -> str:
        """Return the key used for verifying JWTs (public key for RS256, secret for HS256)."""
        if self.jwt_algorithm == "RS256":
            return self._load_rsa_public_key()
        return self.jwt_secret_key

    def _load_rsa_private_key(self) -> str:
        if self.jwt_private_key:
            return self.jwt_private_key
        if self.jwt_private_key_path and os.path.isfile(self.jwt_private_key_path):
            return Path(self.jwt_private_key_path).read_text()
        return self._auto_generate_rsa_keys()[0]

    def _load_rsa_public_key(self) -> str:
        if self.jwt_public_key:
            return self.jwt_public_key
        if self.jwt_public_key_path and os.path.isfile(self.jwt_public_key_path):
            return Path(self.jwt_public_key_path).read_text()
        return self._auto_generate_rsa_keys()[1]

    def _auto_generate_rsa_keys(self) -> tuple:
        """Auto-generate RSA keys for development. In production, provide key files or mount a K8s secret."""
        global _rsa_key_cache
        if _rsa_key_cache:
            return _rsa_key_cache["private"], _rsa_key_cache["public"]

        if os.getenv("JWT_KEY_DIR"):
            cache_dir = Path(os.getenv("JWT_KEY_DIR"))
        elif self.neuranac_env in ("production", "staging"):
            cache_dir = Path("/etc/neuranac/jwt-keys")
        else:
            cache_dir = Path.home() / ".neuranac" / "jwt-keys"
        priv_path = cache_dir / "jwt_private.pem"
        pub_path = cache_dir / "jwt_public.pem"
        if self.neuranac_env in ("production", "staging"):
            _config_logger.warning(
                "JWT RSA keys not provided via JWT_PRIVATE_KEY/JWT_PUBLIC_KEY or file paths. "
                "Auto-generating keys at %s. Mount a Kubernetes secret to persist keys across pod restarts.",
                cache_dir,
            )
        # Check primary cache dir
        if priv_path.exists() and pub_path.exists():
            pair = priv_path.read_text(), pub_path.read_text()
            _rsa_key_cache["private"], _rsa_key_cache["public"] = pair
            return pair
        # Check fallback dir (in case primary was not writable on a previous run)
        import tempfile
        fallback = Path(tempfile.gettempdir()) / "neuranac-jwt-keys"
        fb_priv = fallback / "jwt_private.pem"
        fb_pub = fallback / "jwt_public.pem"
        if fb_priv.exists() and fb_pub.exists():
            pair = fb_priv.read_text(), fb_pub.read_text()
            _rsa_key_cache["private"], _rsa_key_cache["public"] = pair
            return pair
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            priv_pem = private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ).decode()
            pub_pem = private_key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                priv_path.write_text(priv_pem)
                pub_path.write_text(pub_pem)
                os.chmod(str(priv_path), 0o600)
            except PermissionError:
                fallback.mkdir(parents=True, exist_ok=True)
                (fallback / "jwt_private.pem").write_text(priv_pem)
                (fallback / "jwt_public.pem").write_text(pub_pem)
                os.chmod(str(fallback / "jwt_private.pem"), 0o600)
                _config_logger.warning(
                    "Cannot write JWT keys to %s (permission denied), using fallback %s",
                    cache_dir, fallback,
                )
            _rsa_key_cache["private"], _rsa_key_cache["public"] = priv_pem, pub_pem
            return priv_pem, pub_pem
        except ImportError:
            # cryptography not installed — fall back to HS256
            return self.jwt_secret_key, self.jwt_secret_key

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    class Config:
        env_file = ".env"
        case_sensitive = False

    def validate_production_secrets(self):
        """Raise if production environment uses default dev secrets."""
        if self.neuranac_env in ("production", "staging"):
            errors = []
            if "dev_secret_key" in self.api_secret_key or len(self.api_secret_key) < 32:
                errors.append("API_SECRET_KEY must be changed from default and be >= 32 chars")
            if "dev_jwt_secret" in self.jwt_secret_key or len(self.jwt_secret_key) < 64:
                errors.append("JWT_SECRET_KEY must be changed from default and be >= 64 chars")
            if self.postgres_password in ("neuranac_dev_password", "changeme_postgres_password"):
                errors.append("POSTGRES_PASSWORD must be changed from default")
            if self.redis_password in ("neuranac_dev_password", "changeme_redis_password"):
                errors.append("REDIS_PASSWORD must be changed from default")
            if not (self.jwt_private_key or self.jwt_private_key_path):
                errors.append(
                    "JWT_PRIVATE_KEY or JWT_PRIVATE_KEY_PATH should be set in production. "
                    "Auto-generated keys in /tmp are lost on pod restart, invalidating all tokens. "
                    "Mount a Kubernetes secret at JWT_KEY_DIR (default /etc/neuranac/jwt-keys)."
                )
            if errors:
                raise ValueError(
                    f"FATAL: Insecure configuration for {self.neuranac_env} environment:\n"
                    + "\n".join(f"  - {e}" for e in errors)
                )


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.validate_production_secrets()
    return s

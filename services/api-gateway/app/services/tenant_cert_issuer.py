"""Per-Tenant mTLS Certificate Issuer — zero-trust connector bootstrap.

When a connector activates via an activation code, this service:
  1. Generates a short-lived client certificate (signed by the NeuraNAC internal CA)
  2. Stores the cert metadata in neuranac_connector_trust
  3. Returns the cert + CA to the connector for mTLS communication

The connector then uses these certs for all subsequent API calls and gRPC streams.

Certificate hierarchy:
  NeuraNAC Root CA (self-signed, long-lived)
    └── Tenant Intermediate CA (per-tenant, medium-lived)
         └── Connector Client Cert (per-connector, short-lived, 30-day default)

In development/simulated mode, certificates are generated with a local CA.
In production, this integrates with Vault PKI or cert-manager.
"""
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

logger = structlog.get_logger()

# Default cert validity
DEFAULT_CERT_DAYS = 30
CA_CERT_DAYS = 365 * 5  # 5 years for internal CA


class TenantCertIssuer:
    """Issues per-tenant, per-connector mTLS certificates."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._ca_key: Optional[ec.EllipticCurvePrivateKey] = None
        self._ca_cert: Optional[x509.Certificate] = None

    async def issue_connector_cert(
        self,
        tenant_id: str,
        connector_id: str,
        connector_name: str,
        validity_days: int = DEFAULT_CERT_DAYS,
    ) -> dict:
        """Issue a client certificate for a connector.

        Returns:
            dict with client_cert_pem, client_key_pem, ca_cert_pem, fingerprint, expires_at
        """
        ca_key, ca_cert = self._get_or_create_ca()

        # Generate connector key pair (ECDSA P-256)
        client_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

        # Build subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NeuraNAC"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, f"tenant-{tenant_id[:8]}"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"connector-{connector_id[:8]}-{connector_name}"),
        ])

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires = now + timedelta(days=validity_days)

        # Build certificate
        cert_builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(client_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(expires)
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, key_encipherment=False,
                    content_commitment=False, data_encipherment=False,
                    key_agreement=False, key_cert_sign=False,
                    crl_sign=False, encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=False,
            )
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.UniformResourceIdentifier(
                        f"spiffe://neuranac.local/tenant/{tenant_id}/connector/{connector_id}"
                    ),
                ]),
                critical=False,
            )
        )

        client_cert = cert_builder.sign(ca_key, hashes.SHA256(), default_backend())

        # Serialize
        client_cert_pem = client_cert.public_bytes(serialization.Encoding.PEM).decode()
        client_key_pem = client_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        ca_cert_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode()

        # Fingerprint
        fingerprint = hashlib.sha256(
            client_cert.public_bytes(serialization.Encoding.DER)
        ).hexdigest()

        # Store in DB
        await self.db.execute(text(
            "INSERT INTO neuranac_connector_trust "
            "(tenant_id, connector_id, client_cert_pem, client_key_hash, ca_cert_pem, "
            "trust_status, fingerprint, expires_at) "
            "VALUES (:tid, :cid, :cert, :kh, :ca, 'trusted', :fp, :exp)"
        ), {
            "tid": tenant_id,
            "cid": connector_id,
            "cert": client_cert_pem,
            "kh": hashlib.sha256(client_key_pem.encode()).hexdigest(),
            "ca": ca_cert_pem,
            "fp": fingerprint,
            "exp": expires,
        })
        await self.db.commit()

        logger.info("Connector certificate issued",
                    connector_id=connector_id, tenant_id=tenant_id,
                    fingerprint=fingerprint[:16], expires=str(expires))

        return {
            "client_cert_pem": client_cert_pem,
            "client_key_pem": client_key_pem,
            "ca_cert_pem": ca_cert_pem,
            "fingerprint": fingerprint,
            "expires_at": expires.isoformat(),
        }

    async def revoke_connector_cert(self, connector_id: str) -> bool:
        """Revoke all certificates for a connector."""
        result = await self.db.execute(text(
            "UPDATE neuranac_connector_trust SET trust_status = 'revoked', revoked_at = now() "
            "WHERE connector_id = :cid AND trust_status = 'trusted' RETURNING id"
        ), {"cid": connector_id})
        await self.db.commit()
        rows = result.fetchall()
        if rows:
            logger.info("Connector certs revoked",
                        connector_id=connector_id, count=len(rows))
        return len(rows) > 0

    async def verify_fingerprint(self, fingerprint: str) -> Optional[dict]:
        """Look up a certificate by fingerprint. Returns trust info or None."""
        result = await self.db.execute(text(
            "SELECT ct.id, ct.connector_id, ct.tenant_id, ct.trust_status, "
            "ct.expires_at, c.name as connector_name, c.status as connector_status "
            "FROM neuranac_connector_trust ct "
            "JOIN neuranac_connectors c ON ct.connector_id = c.id "
            "WHERE ct.fingerprint = :fp"
        ), {"fp": fingerprint})
        row = result.fetchone()
        if not row:
            return None

        # Check if expired
        status = row[3]
        if status == "trusted" and row[4] and row[4].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc).replace(tzinfo=None):
            status = "expired"

        return {
            "trust_id": str(row[0]),
            "connector_id": str(row[1]),
            "tenant_id": str(row[2]),
            "trust_status": status,
            "expires_at": row[4].isoformat() if row[4] else None,
            "connector_name": row[5],
            "connector_status": row[6],
            "valid": status == "trusted",
        }

    def _get_or_create_ca(self) -> Tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
        """Get or create the internal CA key pair.

        In production, this would load from Vault or a mounted secret.
        For development, generates an ephemeral CA.
        """
        if self._ca_key and self._ca_cert:
            return self._ca_key, self._ca_cert

        # Check for CA from environment/mounted secret
        ca_key_path = os.getenv("NEURANAC_CA_KEY_PATH")
        ca_cert_path = os.getenv("NEURANAC_CA_CERT_PATH")

        if ca_key_path and ca_cert_path and os.path.exists(ca_key_path):
            with open(ca_key_path, "rb") as f:
                self._ca_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
            with open(ca_cert_path, "rb") as f:
                self._ca_cert = x509.load_pem_x509_certificate(
                    f.read(), default_backend()
                )
            logger.info("Loaded CA from mounted secrets")
        else:
            # Generate ephemeral CA for development
            self._ca_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NeuraNAC Internal CA"),
                x509.NameAttribute(NameOID.COMMON_NAME, "NeuraNAC Root CA (Dev)"),
            ])
            self._ca_cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(self._ca_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc).replace(tzinfo=None))
                .not_valid_after(datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=CA_CERT_DAYS))
                .add_extension(
                    x509.BasicConstraints(ca=True, path_length=1),
                    critical=True,
                )
                .sign(self._ca_key, hashes.SHA256(), default_backend())
            )
            logger.warning("Using ephemeral CA — set NEURANAC_CA_KEY_PATH/NEURANAC_CA_CERT_PATH for production")

        return self._ca_key, self._ca_cert

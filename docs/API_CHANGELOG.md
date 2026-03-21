# NeuraNAC API Changelog

All notable API changes are documented here. The API follows semantic versioning.

## [v1.0.0] — 2026-03-03 (GA Release)

### Added
- **Authentication:** `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`
- **API Key Auth:** `X-API-Key` header and `Authorization: ApiKey <key>` support for service accounts
- **Policies:** Full CRUD at `/api/v1/policies`, `/api/v1/policy-sets`, `/api/v1/authorization-profiles`
- **Network Devices:** CRUD at `/api/v1/network-devices` with shared secret management
- **Endpoints:** `/api/v1/endpoints` — list, search, profile endpoints
- **Sessions:** `/api/v1/sessions` — active and historical RADIUS sessions
- **Certificates:** `/api/v1/certificates` — TLS/EAP certificate management
- **Segmentation:** `/api/v1/segmentation/sgts`, `/api/v1/segmentation/matrix` — TrustSec SGTs
- **Guest Access:** `/api/v1/guest` — guest account lifecycle
- **Posture:** `/api/v1/posture` — posture policy management
- **Identity Sources:** `/api/v1/identity-sources` — LDAP/AD/SAML integration
- **Legacy NAC Integration:**
  - `/api/v1/legacy-nac/connections` — legacy connection management
  - `/api/v1/legacy-nac/sync` — synchronization control
  - `/api/v1/legacy-nac/conflicts` — conflict detection and resolution
  - `/api/v1/legacy-nac/migration` — zero-touch migration wizard
  - `/api/v1/legacy-nac/event-stream` — Event Stream subscriptions
  - `/api/v1/legacy-nac/policies` — AI-assisted policy translation
- **AI Chat:** `/api/v1/ai/chat`, `/api/v1/ai/suggestions` — natural language interface
- **AI Agents:** `/api/v1/ai/agents` — AI agent management
- **AI Data Flow:** `/api/v1/ai/data-flow` — shadow AI detection
- **Diagnostics:** `/api/v1/diagnostics/health`, `/api/v1/diagnostics/db-schema-check`
- **Audit:** `/api/v1/audit` — audit log query
- **Admin:** `/api/v1/admin/users`, `/api/v1/admin/roles` — user/role management
- **Webhooks:** `/api/v1/webhooks` — event webhook configuration
- **SIEM:** `/api/v1/siem` — SIEM integration endpoints
- **Privacy:** `/api/v1/privacy` — data privacy controls (GDPR)
- **Licenses:** `/api/v1/licenses` — license management
- **Nodes:** `/api/v1/nodes` — cluster node management
- **WebSocket:** `ws://HOST:8080/api/v1/ws/events` — real-time event streaming
- **Metrics:** `/metrics` — Prometheus metrics endpoint
- **Health:** `/health`, `/ready` — liveness and readiness probes

### Security
- JWT RS256 asymmetric key authentication
- Refresh token rotation with family-based reuse detection
- RBAC with role-based permission enforcement
- OWASP security headers on all responses
- Input validation middleware (SQL injection, XSS protection)
- Per-endpoint per-tenant rate limiting
- API key authentication for service accounts

### Protocols
- RADIUS Authentication (UDP 1812)
- RADIUS Accounting (UDP 1813)
- RadSec (TLS 2083)
- TACACS+ (TCP 49)
- CoA/Disconnect (UDP 3799)

## API Versioning Policy

- Current version: `v1` (prefix: `/api/v1/`)
- Breaking changes will increment the major version (`v2`)
- Deprecated endpoints will be marked with `Deprecation` header and maintained for 2 major versions
- New features are added as non-breaking extensions to the current version
- Clients should include `Accept: application/json` header

## Rate Limits

| Endpoint Group         | Limit   | Window |
| ---------------------- | ------- | ------ |
| `/api/v1/auth/login`   | 10 req  | 1 min  |
| `/api/v1/auth/refresh` | 30 req  | 1 min  |
| `/api/v1/ai/*`         | 30 req  | 1 min  |
| Default                | 100 req | 1 min  |

## Error Format

All errors follow this JSON structure:
```json
{
  "detail": "Human-readable error message",
  "status_code": 400,
  "error_code": "VALIDATION_ERROR"
}
```

## Migration Guide (for future v2)

When v2 is released:
1. Both `/api/v1/` and `/api/v2/` will be available simultaneously
2. v1 endpoints will return `Deprecation: true` header
3. v1 will be maintained for at least 12 months after v2 GA
4. Migration scripts will be provided for client code updates

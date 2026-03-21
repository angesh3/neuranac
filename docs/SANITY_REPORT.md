# NeuraNAC Sanity Test Report

**Generated:** 2026-03-21 04:32:16 UTC

## Summary

| Metric | Count |
|--------|-------|
| Total Tests | 476 |
| Passed | 464 |
| Failed | 12 |
| Skipped | 0 |
| Pass Rate | 97.5% |

## Phase: INFRA (4/4 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| infra-01 | GET /health | GET | `GET /health` | 200 | PASS |
| infra-02 | GET /ready | GET | `GET /ready` | 200 | PASS |
| infra-03 | GET /metrics | GET | `GET /metrics` | 200 | PASS |
| infra-04 | GET /openapi.json | GET | `GET /api/v1/openapi.json` | 200 | PASS |

## Phase: AUTH (3/3 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| auth-01 | POST /auth/login | POST | `POST /api/v1/auth/login` | 200 | PASS |
| auth-02 | POST /auth/refresh | POST | `POST /api/v1/auth/refresh` | 401 | PASS |
| auth-03 | POST /auth/logout | POST | `POST /api/v1/auth/logout` | 200 | PASS |

## Phase: POLICIES (11/11 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| pol-01 | GET /policies/ | GET | `GET /api/v1/policies/` | 200 | PASS |
| pol-02 | POST /policies/ | POST | `POST /api/v1/policies/` | 201 | PASS |
| pol-03 | GET /policies/{id} | GET | `GET /api/v1/policies/2a8a6b22-c701-4a7b-b465-8faca7c3a9fd` | 200 | PASS |
| pol-04 | PUT /policies/{id} | PUT | `PUT /api/v1/policies/2a8a6b22-c701-4a7b-b465-8faca7c3a9fd` | 200 | PASS |
| pol-05 | POST /policies/{id}/rules | POST | `POST /api/v1/policies/2a8a6b22-c701-4a7b-b465-8faca7c3a9fd/rules` | 201 | PASS |
| pol-06 | GET /policies/{id}/rules | GET | `GET /api/v1/policies/2a8a6b22-c701-4a7b-b465-8faca7c3a9fd/rules` | 200 | PASS |
| pol-07 | PUT /policies/{id}/rules/{rid} | PUT | `PUT /api/v1/policies/2a8a6b22-c701-4a7b-b465-8faca7c3a9fd/rules/af2a0eb1-f104-4914-9303-34d68d7587d9` | 200 | PASS |
| pol-08 | DELETE /policies/{id}/rules/{rid} | DELETE | `DELETE /api/v1/policies/2a8a6b22-c701-4a7b-b465-8faca7c3a9fd/rules/af2a0eb1-f104-4914-9303-34d68d7587d9` | 204 | PASS |
| pol-09 | DELETE /policies/{id} | DELETE | `DELETE /api/v1/policies/2a8a6b22-c701-4a7b-b465-8faca7c3a9fd` | 204 | PASS |
| pol-10 | GET /policies/auth-profiles/ | GET | `GET /api/v1/policies/auth-profiles/` | 200 | PASS |
| pol-11 | POST /policies/auth-profiles/ | POST | `POST /api/v1/policies/auth-profiles/` | 201 | PASS |

## Phase: IDENTITY (11/11 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| id-01 | GET /identity-sources/ | GET | `GET /api/v1/identity-sources/` | 200 | PASS |
| id-02 | POST /identity-sources/ | POST | `POST /api/v1/identity-sources/` | 201 | PASS |
| id-03 | GET /identity-sources/{id} | GET | `GET /api/v1/identity-sources/55f04e83-0630-44fa-92ce-6f49efb92e48` | 200 | PASS |
| id-04 | PUT /identity-sources/{id} | PUT | `PUT /api/v1/identity-sources/55f04e83-0630-44fa-92ce-6f49efb92e48` | 200 | PASS |
| id-05 | POST /identity-sources/{id}/test | POST | `POST /api/v1/identity-sources/55f04e83-0630-44fa-92ce-6f49efb92e48/test` | 200 | PASS |
| id-06 | POST /identity-sources/{id}/sync | POST | `POST /api/v1/identity-sources/55f04e83-0630-44fa-92ce-6f49efb92e48/sync` | 200 | PASS |
| id-07 | DELETE /identity-sources/{id} | DELETE | `DELETE /api/v1/identity-sources/55f04e83-0630-44fa-92ce-6f49efb92e48` | 204 | PASS |
| id-08 | POST /identity-sources/saml/initiate | POST | `POST /api/v1/identity-sources/saml/initiate` | 400 | PASS |
| id-09 | POST /identity-sources/saml/acs | POST | `POST /api/v1/identity-sources/saml/acs` | 400 | PASS |
| id-10 | POST /identity-sources/oauth/initiate | POST | `POST /api/v1/identity-sources/oauth/initiate` | 422 | PASS |
| id-11 | POST /identity-sources/oauth/callback | POST | `POST /api/v1/identity-sources/oauth/callback` | 422 | PASS |

## Phase: NETWORK (6/6 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| net-01 | GET /network-devices/ | GET | `GET /api/v1/network-devices/` | 200 | PASS |
| net-02 | POST /network-devices/ | POST | `POST /api/v1/network-devices/` | 201 | PASS |
| net-03 | GET /network-devices/{id} | GET | `GET /api/v1/network-devices/ef9cda92-2717-49c1-8897-de6faf75bb5c` | 200 | PASS |
| net-04 | PUT /network-devices/{id} | PUT | `PUT /api/v1/network-devices/ef9cda92-2717-49c1-8897-de6faf75bb5c` | 200 | PASS |
| net-05 | DELETE /network-devices/{id} | DELETE | `DELETE /api/v1/network-devices/ef9cda92-2717-49c1-8897-de6faf75bb5c` | 204 | PASS |
| net-06 | POST /network-devices/discover | POST | `POST /api/v1/network-devices/discover` | 200 | PASS |

## Phase: ENDPOINTS (7/7 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ep-01 | GET /endpoints/ | GET | `GET /api/v1/endpoints/` | 200 | PASS |
| ep-02 | POST /endpoints/ | POST | `POST /api/v1/endpoints/` | 201 | PASS |
| ep-03 | GET /endpoints/{id} | GET | `GET /api/v1/endpoints/2ea7e850-f4bc-4b9a-8963-0d49a1029760` | 200 | PASS |
| ep-04 | PUT /endpoints/{id} | PUT | `PUT /api/v1/endpoints/2ea7e850-f4bc-4b9a-8963-0d49a1029760` | 200 | PASS |
| ep-05 | POST /endpoints/{id}/profile | POST | `POST /api/v1/endpoints/2ea7e850-f4bc-4b9a-8963-0d49a1029760/profile` | 200 | PASS |
| ep-06 | GET /endpoints/by-mac/AA:BB:CC:DD:EE:99 | GET | `GET /api/v1/endpoints/by-mac/AA:BB:CC:DD:EE:99` | 200 | PASS |
| ep-07 | DELETE /endpoints/{id} | DELETE | `DELETE /api/v1/endpoints/2ea7e850-f4bc-4b9a-8963-0d49a1029760` | 204 | PASS |

## Phase: SEGMENTATION (6/6 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| seg-01 | GET /segmentation/sgts | GET | `GET /api/v1/segmentation/sgts` | 200 | PASS |
| seg-02 | POST /segmentation/sgts | POST | `POST /api/v1/segmentation/sgts` | 201 | PASS |
| seg-03 | GET /segmentation/sgts/{id} | GET | `GET /api/v1/segmentation/sgts/682973e9-e6e2-4ce5-8ad9-f50d9acc4128` | 200 | PASS |
| seg-04 | PUT /segmentation/sgts/{id} | PUT | `PUT /api/v1/segmentation/sgts/682973e9-e6e2-4ce5-8ad9-f50d9acc4128` | 200 | PASS |
| seg-05 | DELETE /segmentation/sgts/{id} | DELETE | `DELETE /api/v1/segmentation/sgts/682973e9-e6e2-4ce5-8ad9-f50d9acc4128` | 204 | PASS |
| seg-06 | GET /segmentation/matrix | GET | `GET /api/v1/segmentation/matrix` | 200 | PASS |

## Phase: CERTS (6/6 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| cert-01 | GET /certificates/cas | GET | `GET /api/v1/certificates/cas` | 200 | PASS |
| cert-02 | POST /certificates/cas | POST | `POST /api/v1/certificates/cas` | 201 | PASS |
| cert-03 | GET /certificates/ | GET | `GET /api/v1/certificates/` | 200 | PASS |
| cert-04 | POST /certificates/ | POST | `POST /api/v1/certificates/` | 201 | PASS |
| cert-05 | GET /certificates/{id} | GET | `GET /api/v1/certificates/11082c47-4698-4f24-a256-4079152195c5` | 200 | PASS |
| cert-06 | POST /certificates/{id}/revoke | POST | `POST /api/v1/certificates/11082c47-4698-4f24-a256-4079152195c5/revoke` | 200 | PASS |

## Phase: SESSIONS (2/2 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| sess-01 | GET /sessions/ | GET | `GET /api/v1/sessions/` | 200 | PASS |
| sess-02 | GET /sessions/active/count | GET | `GET /api/v1/sessions/active/count` | 200 | PASS |

## Phase: GUEST (12/12 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| guest-01 | GET /guest/portals | GET | `GET /api/v1/guest/portals` | 200 | PASS |
| guest-02 | POST /guest/portals | POST | `POST /api/v1/guest/portals` | 201 | PASS |
| guest-03 | GET /guest/portals/{id} | GET | `GET /api/v1/guest/portals/9f0f9d15-b303-46c0-8aca-36233080c835` | 200 | PASS |
| guest-04 | DELETE /guest/portals/{id} | DELETE | `DELETE /api/v1/guest/portals/9f0f9d15-b303-46c0-8aca-36233080c835` | 204 | PASS |
| guest-05 | GET /guest/accounts | GET | `GET /api/v1/guest/accounts` | 200 | PASS |
| guest-06 | POST /guest/accounts | POST | `POST /api/v1/guest/accounts` | 201 | PASS |
| guest-07 | DELETE /guest/accounts/{username} | DELETE | `DELETE /api/v1/guest/accounts/sanity_guest` | 204 | PASS |
| guest-08 | GET /guest/sponsor-groups | GET | `GET /api/v1/guest/sponsor-groups` | 200 | PASS |
| guest-09 | GET /guest/captive-portal/page | GET | `GET /api/v1/guest/captive-portal/page` | 200 | PASS |
| guest-10 | POST /guest/captive-portal/authenticate | POST | `POST /api/v1/guest/captive-portal/authenticate` | 200 | PASS |
| guest-11 | POST /guest/byod/register | POST | `POST /api/v1/guest/byod/register` | 201 | PASS |
| guest-12 | GET /guest/byod/registrations | GET | `GET /api/v1/guest/byod/registrations` | 200 | PASS |

## Phase: POSTURE (6/6 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| post-01 | GET /posture/policies | GET | `GET /api/v1/posture/policies` | 200 | PASS |
| post-02 | POST /posture/policies | POST | `POST /api/v1/posture/policies` | 201 | PASS |
| post-03 | GET /posture/policies/{id} | GET | `GET /api/v1/posture/policies/df560316-e0d9-45c5-9d27-5da32e7693bc` | 200 | PASS |
| post-04 | DELETE /posture/policies/{id} | DELETE | `DELETE /api/v1/posture/policies/df560316-e0d9-45c5-9d27-5da32e7693bc` | 204 | PASS |
| post-05 | POST /posture/assess | POST | `POST /api/v1/posture/assess` | 200 | PASS |
| post-06 | GET /posture/results | GET | `GET /api/v1/posture/results` | 200 | PASS |

## Phase: SIEM (8/8 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| siem-01 | GET /siem/destinations | GET | `GET /api/v1/siem/destinations` | 200 | PASS |
| siem-02 | POST /siem/destinations | POST | `POST /api/v1/siem/destinations` | 201 | PASS |
| siem-03 | POST /siem/destinations/{id}/test | POST | `POST /api/v1/siem/destinations/f91f0787-e334-45c6-9aa6-a677f45da668/test` | 200 | PASS |
| siem-04 | DELETE /siem/destinations/{id} | DELETE | `DELETE /api/v1/siem/destinations/f91f0787-e334-45c6-9aa6-a677f45da668` | 204 | PASS |
| siem-05 | POST /siem/forward | POST | `POST /api/v1/siem/forward` | 200 | PASS |
| siem-06 | GET /siem/soar/playbooks | GET | `GET /api/v1/siem/soar/playbooks` | 200 | PASS |
| siem-07 | POST /siem/soar/playbooks | POST | `POST /api/v1/siem/soar/playbooks` | 201 | PASS |
| siem-08 | POST /siem/soar/playbooks/{id}/trigger | POST | `POST /api/v1/siem/soar/playbooks/0bdb49f3-c192-4a5d-8a98-1e11e72d4d9d/trigger` | 200 | PASS |

## Phase: WEBHOOKS (11/11 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| wh-01 | GET /webhooks/ | GET | `GET /api/v1/webhooks/` | 200 | PASS |
| wh-02 | POST /webhooks/ | POST | `POST /api/v1/webhooks/` | 201 | PASS |
| wh-03 | GET /webhooks/{id} | GET | `GET /api/v1/webhooks/wh-1` | 200 | PASS |
| wh-04 | PUT /webhooks/{id} | PUT | `PUT /api/v1/webhooks/wh-1` | 200 | PASS |
| wh-05 | POST /webhooks/{id}/test | POST | `POST /api/v1/webhooks/wh-1/test` | 200 | PASS |
| wh-06 | DELETE /webhooks/{id} | DELETE | `DELETE /api/v1/webhooks/wh-1` | 204 | PASS |
| wh-07 | GET /webhooks/plugins | GET | `GET /api/v1/webhooks/plugins` | 200 | PASS |
| wh-08 | POST /webhooks/plugins | POST | `POST /api/v1/webhooks/plugins` | 201 | PASS |
| wh-09 | POST /webhooks/plugins/{id}/enable | POST | `POST /api/v1/webhooks/plugins/plugin-1/enable` | 200 | PASS |
| wh-10 | POST /webhooks/plugins/{id}/disable | POST | `POST /api/v1/webhooks/plugins/plugin-1/disable` | 200 | PASS |
| wh-11 | DELETE /webhooks/plugins/{id} | DELETE | `DELETE /api/v1/webhooks/plugins/plugin-1` | 204 | PASS |

## Phase: PRIVACY (9/9 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| priv-01 | GET /privacy/subjects | GET | `GET /api/v1/privacy/subjects` | 200 | PASS |
| priv-02 | POST /privacy/subjects | POST | `POST /api/v1/privacy/subjects` | 201 | PASS |
| priv-03 | GET /privacy/subjects/{id} | GET | `GET /api/v1/privacy/subjects/fe24dde0-4c01-4172-8538-e3b6a2d01095` | 200 | PASS |
| priv-04 | POST /privacy/subjects/{id}/erasure | POST | `POST /api/v1/privacy/subjects/fe24dde0-4c01-4172-8538-e3b6a2d01095/erasure` | 200 | PASS |
| priv-05 | GET /privacy/consent | GET | `GET /api/v1/privacy/consent` | 200 | PASS |
| priv-06 | POST /privacy/consent | POST | `POST /api/v1/privacy/consent` | 201 | PASS |
| priv-07 | POST /privacy/consent/{id}/revoke | POST | `POST /api/v1/privacy/consent/c1fe7282-5648-438c-8d88-bb7fd4999552/revoke` | 200 | PASS |
| priv-08 | GET /privacy/exports | GET | `GET /api/v1/privacy/exports` | 200 | PASS |
| priv-09 | POST /privacy/exports | POST | `POST /api/v1/privacy/exports` | 201 | PASS |

## Phase: AI (10/10 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai-01 | GET /ai/agents/ | GET | `GET /api/v1/ai/agents/` | 200 | PASS |
| ai-02 | POST /ai/agents/ | POST | `POST /api/v1/ai/agents/` | 201 | PASS |
| ai-03 | GET /ai/agents/{id} | GET | `GET /api/v1/ai/agents/b558a0fb-0f8b-4730-aa49-322e07cb0d4d` | 200 | PASS |
| ai-04 | PUT /ai/agents/{id} | PUT | `PUT /api/v1/ai/agents/b558a0fb-0f8b-4730-aa49-322e07cb0d4d` | 200 | PASS |
| ai-05 | POST /ai/agents/{id}/revoke | POST | `POST /api/v1/ai/agents/b558a0fb-0f8b-4730-aa49-322e07cb0d4d/revoke` | 200 | PASS |
| ai-06 | DELETE /ai/agents/{id} | DELETE | `DELETE /api/v1/ai/agents/b558a0fb-0f8b-4730-aa49-322e07cb0d4d` | 204 | PASS |
| ai-07 | GET /ai/data-flow/services | GET | `GET /api/v1/ai/data-flow/services` | 200 | PASS |
| ai-08 | GET /ai/data-flow/detections | GET | `GET /api/v1/ai/data-flow/detections` | 200 | PASS |
| ai-09 | GET /ai/data-flow/policies | GET | `GET /api/v1/ai/data-flow/policies` | 200 | PASS |
| ai-10 | POST /ai/data-flow/policies | POST | `POST /api/v1/ai/data-flow/policies` | 201 | PASS |

## Phase: AUDIT (4/4 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| aud-01 | GET /audit/ | GET | `GET /api/v1/audit/` | 200 | PASS |
| aud-02 | GET /audit/reports/summary | GET | `GET /api/v1/audit/reports/summary` | 200 | PASS |
| aud-03 | GET /audit/reports/auth | GET | `GET /api/v1/audit/reports/auth` | 200 | PASS |
| aud-04 | GET /audit/verify-chain | GET | `GET /api/v1/audit/verify-chain` | 200 | PASS |

## Phase: DIAGNOSTICS (5/5 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| diag-01 | GET /diagnostics/system-status | GET | `GET /api/v1/diagnostics/system-status` | 200 | PASS |
| diag-02 | GET /diagnostics/radius-live-log | GET | `GET /api/v1/diagnostics/radius-live-log` | 200 | PASS |
| diag-03 | POST /diagnostics/connectivity-test | POST | `POST /api/v1/diagnostics/connectivity-test` | 200 | PASS |
| diag-04 | POST /diagnostics/troubleshoot | POST | `POST /api/v1/diagnostics/troubleshoot` | 422 | PASS |
| diag-05 | POST /diagnostics/support-bundle | POST | `POST /api/v1/diagnostics/support-bundle` | 200 | PASS |

## Phase: LICENSES (4/4 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| lic-01 | GET /licenses/ | GET | `GET /api/v1/licenses/` | 200 | PASS |
| lic-02 | GET /licenses/tiers | GET | `GET /api/v1/licenses/tiers` | 200 | PASS |
| lic-03 | GET /licenses/usage | GET | `GET /api/v1/licenses/usage` | 200 | PASS |
| lic-04 | POST /licenses/activate | POST | `POST /api/v1/licenses/activate` | 200 | PASS |

## Phase: NODES (4/4 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| node-01 | GET /nodes/ | GET | `GET /api/v1/nodes/` | 200 | PASS |
| node-02 | GET /nodes/sync-status | GET | `GET /api/v1/nodes/sync-status` | 200 | PASS |
| node-03 | POST /nodes/sync/trigger | POST | `POST /api/v1/nodes/sync/trigger` | 200 | PASS |
| node-04 | POST /nodes/failover | POST | `POST /api/v1/nodes/failover` | 200 | PASS |

## Phase: SETUP (7/7 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| setup-01 | GET /setup/status | GET | `GET /api/v1/setup/status` | 200 | PASS |
| setup-02 | POST /setup/step/{step_number} | POST | `POST /api/v1/setup/step/1` | 200 | PASS |
| setup-03 | POST /setup/network-scan | POST | `POST /api/v1/setup/network-scan` | 200 | PASS |
| setup-04 | POST /setup/identity-source | POST | `POST /api/v1/setup/identity-source` | 200 | PASS |
| setup-05 | POST /setup/policies/generate | POST | `POST /api/v1/setup/policies/generate` | 200 | PASS |
| setup-06 | POST /setup/network-design/generate | POST | `POST /api/v1/setup/network-design/generate` | 200 | PASS |
| setup-07 | POST /setup/activate | POST | `POST /api/v1/setup/activate` | 200 | PASS |

## Phase: LEGACY_NAC (14/14 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| lnac-01 | GET /legacy-nac/connections | GET | `GET /api/v1/legacy-nac/connections` | 200 | PASS |
| lnac-02 | POST /legacy-nac/connections | POST | `POST /api/v1/legacy-nac/connections` | 201 | PASS |
| lnac-03 | GET /legacy-nac/connections/{id} | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff` | 200 | PASS |
| lnac-04 | PUT /legacy-nac/connections/{id} | PUT | `PUT /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff` | 200 | PASS |
| lnac-05 | POST /legacy-nac/connections/{id}/test | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/test` | 500 | PASS |
| lnac-06 | POST /legacy-nac/connections/{id}/sync | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/sync` | 200 | PASS |
| lnac-07 | GET /legacy-nac/connections/{id}/sync-status | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/sync-status` | 200 | PASS |
| lnac-08 | GET /legacy-nac/connections/{id}/sync-log | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/sync-log` | 200 | PASS |
| lnac-09 | GET /legacy-nac/connections/{id}/entity-map | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/entity-map` | 200 | PASS |
| lnac-10 | POST /legacy-nac/connections/{id}/migration | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/migration` | 400 | PASS |
| lnac-11 | GET /legacy-nac/connections/{id}/migration-status | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/migration-status` | 200 | PASS |
| lnac-12 | GET /legacy-nac/connections/{id}/preview/network_device | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/preview/network_device` | 200 | PASS |
| lnac-13 | GET /legacy-nac/summary | GET | `GET /api/v1/legacy-nac/summary` | 200 | PASS |
| lnac-99 | DELETE /legacy-nac/connections/{id} | DELETE | `DELETE /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff` | 204 | PASS |

## Phase: LEGACY_NAC_ENHANCED (35/35 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| lnacv-01 | POST /legacy-nac/connections/{id}/detect-version | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/detect-version` | 200 | PASS |
| lnacv-02 | GET /legacy-nac/connections/{id}/schedules | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/schedules` | 200 | PASS |
| lnacv-03 | POST /legacy-nac/connections/{id}/schedules | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/schedules` | 201 | PASS |
| lnacv-04 | PUT /legacy-nac/connections/{id}/schedules/{et} | PUT | `PUT /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/schedules/network_device` | 200 | PASS |
| lnacv-05 | POST /legacy-nac/connections/{id}/schedules/run-due | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/schedules/run-due` | 200 | PASS |
| lnacv-06 | DELETE /legacy-nac/connections/{id}/schedules/{et} | DELETE | `DELETE /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/schedules/network_device` | 204 | PASS |
| lnacv-07 | POST /legacy-nac/connections/{id}/event-stream/connect | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/connect` | 200 | PASS |
| lnacv-08 | GET /legacy-nac/connections/{id}/event-stream/status | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/status` | 200 | PASS |
| lnacv-09 | POST /legacy-nac/connections/{id}/event-stream/simulate-event | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/simulate-event?event_type=session_created` | 200 | PASS |
| lnacv-10 | GET /legacy-nac/connections/{id}/event-stream/events | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/events` | 200 | PASS |
| lnacv-11 | POST /legacy-nac/connections/{id}/event-stream/disconnect | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/disconnect` | 200 | PASS |
| lnacv-12 | GET /legacy-nac/connections/{id}/policies/discover | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/policies/discover` | 200 | PASS |
| lnacv-13 | POST /legacy-nac/connections/{id}/policies/translate | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/policies/translate` | 200 | PASS |
| lnacv-14 | POST /legacy-nac/connections/{id}/policies/translate-all | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/policies/translate-all` | 200 | PASS |
| lnacv-15 | GET /legacy-nac/connections/{id}/policies/translations | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/policies/translations` | 200 | PASS |
| lnacv-16 | GET /legacy-nac/connections/{id}/policies/translations/{tid} | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/policies/translations/179669a2-c45d-4926-950e-a38696fc69ac` | 200 | PASS |
| lnacv-17 | POST /legacy-nac/connections/{id}/policies/translations/{tid}/apply | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/policies/translations/179669a2-c45d-4926-950e-a38696fc69ac/apply` | 200 | PASS |
| lnacv-18 | POST /legacy-nac/connections/{id}/conflicts/simulate | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/conflicts/simulate` | 200 | PASS |
| lnacv-19 | GET /legacy-nac/connections/{id}/conflicts | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/conflicts` | 200 | PASS |
| lnacv-20 | GET /legacy-nac/connections/{id}/conflicts/{cid} (first) | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/conflicts?status=unresolved` | 200 | PASS |
| lnacv-21 | POST /legacy-nac/connections/{id}/conflicts/resolve-all | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/conflicts/resolve-all` | 200 | PASS |
| lnacv-22 | POST /legacy-nac/connections/{id}/sync/bidirectional | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/sync/bidirectional` | 200 | PASS |
| lnacv-23 | GET /legacy-nac/multi-connection/overview | GET | `GET /api/v1/legacy-nac/multi-connection/overview` | 200 | PASS |
| lnacv-24 | POST /legacy-nac/connections/{id}/wizard/start | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/wizard/start` | 200 | PASS |
| lnacv-25 | GET /legacy-nac/connections/{id}/wizard/{rid} | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/wizard/547c7a35-b11f-47a8-b6ca-fb9df84750e5` | 200 | PASS |
| lnacv-26 | POST execute-step (step 1) | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/wizard/547c7a35-b11f-47a8-b6ca-fb9df84750e5/execute-step` | 200 | PASS |
| lnacv-27 | POST execute-step (step 2) | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/wizard/547c7a35-b11f-47a8-b6ca-fb9df84750e5/execute-step` | 200 | PASS |
| lnacv-28 | POST execute-step (pause) | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/wizard/547c7a35-b11f-47a8-b6ca-fb9df84750e5/execute-step` | 200 | PASS |
| lnacv-29 | POST execute-step (resume) | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/wizard/547c7a35-b11f-47a8-b6ca-fb9df84750e5/execute-step` | 200 | PASS |
| lnacv-30 | GET /legacy-nac/connections/{id}/wizard (list runs) | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/wizard` | 200 | PASS |
| lnacv-31 | POST create baseline snapshot | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/radius-analysis/snapshot` | 200 | PASS |
| lnacv-32 | POST create current snapshot | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/radius-analysis/snapshot` | 200 | PASS |
| lnacv-33 | GET list snapshots | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/radius-analysis/snapshots` | 200 | PASS |
| lnacv-34 | GET snapshot detail | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/radius-analysis/snapshots/0cbb2f18-46f8-461e-9784-3730a15eee7a` | 200 | PASS |
| lnacv-35 | POST compare snapshots | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/radius-analysis/compare?baseline_id=0cbb2f18-46f8-461e-9784-3730a15eee7a&current_id=d0327315-f6e0-491e-ade7-b1296c85f607` | 200 | PASS |

## Phase: AI_PHASE1 (10/10 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai1-01 | POST /ai/chat (list endpoints) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| ai1-02 | POST /ai/chat (show sessions) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| ai1-03 | POST /ai/chat (system status) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| ai1-04 | POST /ai/chat (navigate) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| ai1-05 | POST /ai/chat (unknown intent) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| ai1-06 | GET /ai/capabilities | GET | `GET /api/v1/ai/capabilities` | 200 | PASS |
| ai1-07 | GET /ai/suggestions (root) | GET | `GET /api/v1/ai/suggestions?route=/` | 200 | PASS |
| ai1-08 | GET /ai/suggestions (policies) | GET | `GET /api/v1/ai/suggestions?route=/policies` | 200 | PASS |
| ai1-09 | GET /ai/suggestions (sessions) | GET | `GET /api/v1/ai/suggestions?route=/sessions` | 200 | PASS |
| ai1-10 | GET /ai/suggestions (diagnostics) | GET | `GET /api/v1/ai/suggestions?route=/diagnostics` | 200 | PASS |

## Phase: AI_PHASE4_RAG (3/3 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai4r-01 | POST /rag/troubleshoot (EAP-TLS) | POST | `POST /api/v1/ai/rag/troubleshoot` | 200 | PASS |
| ai4r-02 | POST /rag/troubleshoot (VLAN) | POST | `POST /api/v1/ai/rag/troubleshoot` | 200 | PASS |
| ai4r-03 | POST /rag/troubleshoot (CoA) | POST | `POST /api/v1/ai/rag/troubleshoot` | 200 | PASS |

## Phase: AI_PHASE4_TRAIN (2/2 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai4t-01 | POST /training/sample | POST | `POST /api/v1/ai/training/sample` | 200 | PASS |
| ai4t-02 | GET /training/stats | GET | `GET /api/v1/ai/training/stats` | 200 | PASS |

## Phase: AI_PHASE4_SQL (3/3 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai4s-01 | POST /nl-sql/query (sessions) | POST | `POST /api/v1/ai/nl-sql/query` | 200 | PASS |
| ai4s-02 | POST /nl-sql/query (endpoints) | POST | `POST /api/v1/ai/nl-sql/query` | 200 | PASS |
| ai4s-03 | POST /nl-sql/query (certs) | POST | `POST /api/v1/ai/nl-sql/query` | 200 | PASS |

## Phase: AI_PHASE4_RISK (3/3 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai4k-01 | GET /risk/thresholds | GET | `GET /api/v1/ai/risk/thresholds` | 200 | PASS |
| ai4k-02 | POST /risk/feedback | POST | `POST /api/v1/ai/risk/feedback` | 200 | PASS |
| ai4k-03 | GET /risk/adaptive-stats | GET | `GET /api/v1/ai/risk/adaptive-stats` | 200 | PASS |

## Phase: AI_PHASE4_TLS (7/7 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai4f-01 | POST /tls/analyze-ja3 (known) | POST | `POST /api/v1/ai/tls/analyze-ja3` | 200 | PASS |
| ai4f-02 | POST /tls/analyze-ja3 (unknown) | POST | `POST /api/v1/ai/tls/analyze-ja3` | 200 | PASS |
| ai4f-03 | POST /tls/analyze-ja4 | POST | `POST /api/v1/ai/tls/analyze-ja4` | 200 | PASS |
| ai4f-04 | POST /tls/compute-ja3 | POST | `POST /api/v1/ai/tls/compute-ja3` | 200 | PASS |
| ai4f-05 | POST /tls/custom-signature | POST | `POST /api/v1/ai/tls/custom-signature` | 200 | PASS |
| ai4f-06 | GET /tls/detections | GET | `GET /api/v1/ai/tls/detections` | 200 | PASS |
| ai4f-07 | GET /tls/stats | GET | `GET /api/v1/ai/tls/stats` | 200 | PASS |

## Phase: AI_PHASE4_CAP (4/4 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai4c-01 | POST /capacity/record (auth_rate) | POST | `POST /api/v1/ai/capacity/record` | 200 | PASS |
| ai4c-02 | POST /capacity/record (endpoint_count) | POST | `POST /api/v1/ai/capacity/record` | 200 | PASS |
| ai4c-03 | GET /capacity/metrics | GET | `GET /api/v1/ai/capacity/metrics` | 200 | PASS |
| ai4c-04 | GET /capacity/forecast | GET | `GET /api/v1/ai/capacity/forecast` | 200 | PASS |

## Phase: AI_PHASE4_PB (7/7 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai4p-01 | GET /playbooks | GET | `GET /api/v1/ai/playbooks` | 200 | PASS |
| ai4p-02 | GET /playbooks/{id} (auth failure) | GET | `GET /api/v1/ai/playbooks/pb-auth-failure-lockout` | 200 | PASS |
| ai4p-03 | GET /playbooks/{id} (shadow ai) | GET | `GET /api/v1/ai/playbooks/pb-shadow-ai-block` | 200 | PASS |
| ai4p-04 | POST /playbooks (custom) | POST | `POST /api/v1/ai/playbooks` | 200 | PASS |
| ai4p-05 | POST /playbooks/{id}/execute | POST | `POST /api/v1/ai/playbooks/pb-auth-failure-lockout/execute` | 200 | PASS |
| ai4p-06 | GET /playbooks/executions/list | GET | `GET /api/v1/ai/playbooks/executions/list` | 200 | PASS |
| ai4p-07 | GET /playbooks/stats/summary | GET | `GET /api/v1/ai/playbooks/stats/summary` | 200 | PASS |

## Phase: AI_PHASE4_MDL (6/6 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ai4m-01 | POST /models/register (profiler v1) | POST | `POST /api/v1/ai/models/register` | 200 | PASS |
| ai4m-02 | POST /models/register (profiler v2) | POST | `POST /api/v1/ai/models/register` | 200 | PASS |
| ai4m-03 | GET /models | GET | `GET /api/v1/ai/models` | 200 | PASS |
| ai4m-04 | POST /models/experiments | POST | `POST /api/v1/ai/models/experiments` | 200 | PASS |
| ai4m-05 | GET /models/experiments | GET | `GET /api/v1/ai/models/experiments` | 200 | PASS |
| ai4m-06 | GET /models/stats | GET | `GET /api/v1/ai/models/stats` | 200 | PASS |

## Phase: ADMIN (8/8 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| adm-01 | GET /admin/users | GET | `GET /api/v1/admin/users` | 200 | PASS |
| adm-02 | POST /admin/users | POST | `POST /api/v1/admin/users` | 201 | PASS |
| adm-03 | GET /admin/users/{id} | GET | `GET /api/v1/admin/users/ace25296-0efe-4da7-bc8c-f396c111f123` | 200 | PASS |
| adm-04 | DELETE /admin/users/{id} | DELETE | `DELETE /api/v1/admin/users/ace25296-0efe-4da7-bc8c-f396c111f123` | 204 | PASS |
| adm-05 | GET /admin/roles | GET | `GET /api/v1/admin/roles` | 200 | PASS |
| adm-06 | POST /admin/roles | POST | `POST /api/v1/admin/roles` | 201 | PASS |
| adm-07 | GET /admin/tenants | GET | `GET /api/v1/admin/tenants` | 200 | PASS |
| adm-08 | POST /admin/tenants | POST | `POST /api/v1/admin/tenants` | 500 | PASS |

## Phase: SESSIONS_EXT (3/3 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| sess-03 | GET /sessions/{id} (404) | GET | `GET /api/v1/sessions/00000000-0000-0000-0000-000000000001` | 404 | PASS |
| sess-04 | POST /sessions/{id}/disconnect | POST | `POST /api/v1/sessions/00000000-0000-0000-0000-000000000001/disconnect` | 404 | PASS |
| sess-05 | POST /sessions/{id}/reauthenticate | POST | `POST /api/v1/sessions/00000000-0000-0000-0000-000000000001/reauthenticate` | 404 | PASS |

## Phase: AUDIT_EXT (1/1 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| aud-05 | GET /audit/{log_id} (404) | GET | `GET /api/v1/audit/00000000-0000-0000-0000-000000000001` | 404 | PASS |

## Phase: DB_SETUP (8/8 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| dbs-01 | GET /diagnostics/db-schema-check | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| dbs-02 | V001 tables exist | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| dbs-03 | V002 tables exist | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| dbs-04 | V003 tables exist | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| dbs-05 | Extensions loaded | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| dbs-06 | Singleton rows exist | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| dbs-07 | Seed data populated | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| dbs-08 | ALTER columns applied | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |

## Phase: GAP1_EVENT_STREAM (7/7 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| gap1-01 | POST /legacy-nac/{id}/event-stream/connect (consumer) | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/connect` | 404 | PASS |
| gap1-02 | GET /legacy-nac/{id}/event-stream/status (consumer) | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/status` | 404 | PASS |
| gap1-03 | POST simulate session_created | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/simulate-event?event_type=session_created` | 500 | PASS |
| gap1-04 | POST simulate session_terminated | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/simulate-event?event_type=session_terminated` | 500 | PASS |
| gap1-05 | POST simulate radius_failure | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/simulate-event?event_type=radius_failure` | 500 | PASS |
| gap1-06 | GET /legacy-nac/{id}/event-stream/events (after sim) | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/events?limit=10` | 200 | PASS |
| gap1-07 | POST /legacy-nac/{id}/event-stream/disconnect (consumer) | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/event-stream/disconnect` | 200 | PASS |

## Phase: GAP2_HUB_SPOKE (5/5 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| gap2-01 | GET /nodes/ (hub-spoke) | GET | `GET /api/v1/nodes/` | 200 | PASS |
| gap2-02 | GET /nodes/sync-status (hub-spoke) | GET | `GET /api/v1/nodes/sync-status` | 200 | PASS |
| gap2-03 | POST /nodes/sync/trigger (hub-spoke) | POST | `POST /api/v1/nodes/sync/trigger` | 200 | PASS |
| gap2-04 | POST /nodes/failover (hub-spoke) | POST | `POST /api/v1/nodes/failover` | 200 | PASS |
| gap2-05 | GET /legacy-nac/multi-connection/overview (hub-spoke) | GET | `GET /api/v1/legacy-nac/multi-connection/overview` | 200 | PASS |

## Phase: GAP3_MTLS (2/2 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| gap3-01 | GET /certificates/cas (mTLS) | GET | `GET /api/v1/certificates/cas` | 200 | PASS |
| gap3-02 | POST /certificates/ (mTLS cert) | POST | `POST /api/v1/certificates/` | 201 | PASS |

## Phase: GAP4_CURSOR_RESYNC (3/3 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| gap4-01 | GET /legacy-nac/connections (cursor resync) | GET | `GET /api/v1/legacy-nac/connections` | 200 | PASS |
| gap4-02 | POST /legacy-nac/{id}/sync (full resync) | POST | `POST /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/sync` | 404 | PASS |
| gap4-03 | GET /legacy-nac/{id}/sync-status (cursor) | GET | `GET /api/v1/legacy-nac/connections/9c3b6d94-fbf8-4630-9cc3-55125f0626ff/sync-status` | 200 | PASS |

## Phase: GAP5_COMPRESSION (2/2 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| gap5-01 | GET /policies (Accept-Encoding: gzip) | GET | `GET /api/v1/policies/` | 200 | PASS |
| gap5-02 | GET /endpoints (Accept-Encoding: gzip) | GET | `GET /api/v1/endpoints/` | 200 | PASS |

## Phase: GAP6_NATS (4/4 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| gap6-01 | GET /diagnostics/system-status (NATS check) | GET | `GET /api/v1/diagnostics/system-status` | 200 | PASS |
| gap6-02 | GET /health (NATS liveness) | GET | `GET /health` | 200 | PASS |
| gap6-03 | GET /sessions/active/count (NATS sessions) | GET | `GET /api/v1/sessions/active/count` | 200 | PASS |
| gap6-04 | GET /nodes/sync-status (NATS sync) | GET | `GET /api/v1/nodes/sync-status` | 200 | PASS |

## Phase: GAP7_WEBSOCKET (2/2 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| gap7-01 | GET /diagnostics/system-status (WS check) | GET | `GET /api/v1/diagnostics/system-status` | 200 | PASS |
| gap7-02 | GET /health (WS liveness) | GET | `GET /health` | 200 | PASS |

## Phase: AI_ENGINE_DIRECT (11/15 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| aid-01 | POST /profile (AI Engine direct) | POST | `POST /api/v1/profile` | 200 | PASS |
| aid-02 | POST /risk-score (AI Engine direct) | POST | `POST /api/v1/risk-score` | 200 | PASS |
| aid-03 | POST /shadow-ai/detect (AI Engine direct) | POST | `POST /api/v1/shadow-ai/detect` | 200 | PASS |
| aid-04 | POST /nlp/translate (AI Engine direct) | POST | `POST /api/v1/nlp/translate` | 200 | PASS |
| aid-05 | POST /troubleshoot (AI Engine direct) | POST | `POST /api/v1/troubleshoot` | 200 | PASS |
| aid-06 | POST /anomaly/analyze (AI Engine direct) | POST | `POST /api/v1/anomaly/analyze` | 200 | PASS |
| aid-07 | POST /drift/record (AI Engine direct) | POST | `POST /api/v1/drift/record` | 200 | PASS |
| aid-08 | GET /drift/analyze (AI Engine direct) | GET | `GET /api/v1/drift/analyze` | 200 | PASS |
| aid-09 | POST /ai/chat (AI Engine direct) | POST | `POST /api/v1/ai/chat` | 404 | **FAIL** |
| aid-10 | GET /ai/capabilities (AI Engine direct) | GET | `GET /api/v1/ai/capabilities` | 404 | **FAIL** |
| aid-11 | GET /health (AI Engine direct) | GET | `GET /health` | 200 | PASS |
| aid-12 | POST /training/train (AI Engine direct) | POST | `POST /api/v1/training/train` | 404 | **FAIL** |
| aid-13 | POST /models/experiments/{id}/stop | POST | `POST /api/v1/models/experiments/profiler-ab-test/stop` | 404 | PASS |
| gap-p0-05 | AI Engine: /health passes w/o key | GET | `GET /health` | 200 | PASS |
| gap-p0-06 | AI Engine: protected endpoint rejects w/o key (→ 401) | POST | `POST /api/v1/profile` | 422 | **FAIL** |

## Phase: EXTRA_COVERAGE (11/11 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| xtra-01 | GET /policies/auth-profiles/ (extra) | GET | `GET /api/v1/policies/auth-profiles/` | 200 | PASS |
| xtra-02 | GET /segmentation/matrix (extra) | GET | `GET /api/v1/segmentation/matrix` | 200 | PASS |
| xtra-03 | GET /posture/results (extra) | GET | `GET /api/v1/posture/results` | 200 | PASS |
| xtra-04 | POST /siem/forward (extra) | POST | `POST /api/v1/siem/forward` | 200 | PASS |
| xtra-05 | GET /guest/captive-portal/page (extra) | GET | `GET /api/v1/guest/captive-portal/page` | 200 | PASS |
| xtra-06 | GET /guest/byod/registrations (extra) | GET | `GET /api/v1/guest/byod/registrations` | 200 | PASS |
| xtra-07 | GET /privacy/consent (extra) | GET | `GET /api/v1/privacy/consent` | 200 | PASS |
| xtra-08 | GET /licenses/usage (extra) | GET | `GET /api/v1/licenses/usage` | 200 | PASS |
| xtra-09 | POST /diagnostics/connectivity-test (extra) | POST | `POST /api/v1/diagnostics/connectivity-test` | 200 | PASS |
| xtra-10 | GET /legacy-nac/summary (extra) | GET | `GET /api/v1/legacy-nac/summary` | 200 | PASS |
| xtra-11 | GET /setup/status (extra) | GET | `GET /api/v1/setup/status` | 200 | PASS |

## Phase: GAP_REMEDIATION (15/15 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| gap-p0-01 | Auth: protected endpoint returns 200 (authed) or 401 (no token) | GET | `GET /api/v1/policies/` | 200 | PASS |
| gap-p0-02 | Auth: public /health passes (→ 200) | GET | `GET /health` | 200 | PASS |
| gap-p0-03 | Auth: public /api/v1/auth/login passes (→ 401/422) | POST | `POST /api/v1/auth/login` | 401 | PASS |
| gap-p0-04 | Auth: public /api/v1/setup/status passes | GET | `GET /api/v1/setup/status` | 200 | PASS |
| gap-p1-01 | WS events status endpoint | GET | `GET /api/v1/ws/events/status` | 200 | PASS |
| gap-p1-02 | GET /metrics returns prometheus format | GET | `GET /metrics` | 200 | PASS |
| gap-p1-03 | SIEM page route accessible | GET | `GET /api/v1/siem/destinations` | 200 | PASS |
| gap-p1-04 | Webhooks page route accessible | GET | `GET /api/v1/webhooks/` | 200 | PASS |
| gap-p1-05 | Licenses page route accessible | GET | `GET /api/v1/licenses/` | 200 | PASS |
| gap-p2-01 | CORS preflight OPTIONS passes | OPTIONS | `OPTIONS /api/v1/policies/` | 405 | PASS |
| gap-p2-02 | Posture policies supports skip/limit | GET | `GET /api/v1/posture/policies?skip=0&limit=5` | 200 | PASS |
| gap-p2-03 | Admin roles supports skip/limit | GET | `GET /api/v1/admin/roles?skip=0&limit=5` | 200 | PASS |
| gap-p2-04 | Admin tenants supports skip/limit | GET | `GET /api/v1/admin/tenants?skip=0&limit=5` | 200 | PASS |
| gap-p2-05 | Guest portals supports skip/limit | GET | `GET /api/v1/guest/portals?skip=0&limit=5` | 200 | PASS |
| gap-p2-06 | Privacy exports supports skip/limit | GET | `GET /api/v1/privacy/exports?skip=0&limit=5` | 200 | PASS |

## Phase: WEB (35/35 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| web-01 | GET / | GET | `GET /` | 200 | PASS |
| web-02 | GET /dashboard | GET | `GET /dashboard` | 200 | PASS |
| web-03 | GET /policies | GET | `GET /policies` | 200 | PASS |
| web-04 | GET /identity | GET | `GET /identity` | 200 | PASS |
| web-05 | GET /network-devices | GET | `GET /network-devices` | 200 | PASS |
| web-06 | GET /endpoints | GET | `GET /endpoints` | 200 | PASS |
| web-07 | GET /segmentation | GET | `GET /segmentation` | 200 | PASS |
| web-08 | GET /sessions | GET | `GET /sessions` | 200 | PASS |
| web-09 | GET /guest-access | GET | `GET /guest-access` | 200 | PASS |
| web-10 | GET /certificates | GET | `GET /certificates` | 200 | PASS |
| web-11 | GET /posture | GET | `GET /posture` | 200 | PASS |
| web-12 | GET /diagnostics | GET | `GET /diagnostics` | 200 | PASS |
| web-13 | GET /legacy-nac | GET | `GET /legacy-nac` | 200 | PASS |
| web-14 | GET /legacy-nac/wizard | GET | `GET /legacy-nac/wizard` | 200 | PASS |
| web-15 | GET /legacy-nac/conflicts | GET | `GET /legacy-nac/conflicts` | 200 | PASS |
| web-16 | GET /legacy-nac/radius-analysis | GET | `GET /legacy-nac/radius-analysis` | 200 | PASS |
| web-17 | GET /siem | GET | `GET /siem` | 200 | PASS |
| web-18 | GET /webhooks | GET | `GET /webhooks` | 200 | PASS |
| web-19 | GET /privacy | GET | `GET /privacy` | 200 | PASS |
| web-20 | GET /ai-agents | GET | `GET /ai-agents` | 200 | PASS |
| web-21 | GET /audit | GET | `GET /audit` | 200 | PASS |
| web-22 | GET /licenses | GET | `GET /licenses` | 200 | PASS |
| web-23 | GET /nodes | GET | `GET /nodes` | 200 | PASS |
| web-24 | GET /setup | GET | `GET /setup` | 200 | PASS |
| web-25 | GET /admin | GET | `GET /admin` | 200 | PASS |
| web-26 | GET /settings | GET | `GET /settings` | 200 | PASS |
| web-27 | GET /ai/data-flow | GET | `GET /ai/data-flow` | 200 | PASS |
| web-28 | GET /ai/shadow | GET | `GET /ai/shadow` | 200 | PASS |
| web-29 | GET /legacy-nac | GET | `GET /legacy-nac` | 200 | PASS |
| web-30 | GET /legacy-nac/wizard | GET | `GET /legacy-nac/wizard` | 200 | PASS |
| web-31 | GET /legacy-nac/conflicts | GET | `GET /legacy-nac/conflicts` | 200 | PASS |
| web-32 | GET /legacy-nac/radius-analysis | GET | `GET /legacy-nac/radius-analysis` | 200 | PASS |
| web-33 | GET /legacy-nac/event-stream | GET | `GET /legacy-nac/event-stream` | 200 | PASS |
| web-34 | GET /legacy-nac/policies | GET | `GET /legacy-nac/policies` | 200 | PASS |
| web-35 | GET /topology | GET | `GET /topology` | 200 | PASS |

## Phase: TOPOLOGY (10/10 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| topo-01 | GET /topology/ (physical) | GET | `GET /api/v1/topology/?view=physical` | 200 | PASS |
| topo-02 | GET /topology/ (logical) | GET | `GET /api/v1/topology/?view=logical` | 200 | PASS |
| topo-03 | GET /topology/ (dataflow) | GET | `GET /api/v1/topology/?view=dataflow` | 200 | PASS |
| topo-04 | GET /topology/ (legacy_nac) | GET | `GET /api/v1/topology/?view=legacy_nac` | 200 | PASS |
| topo-05 | GET /topology/health-matrix | GET | `GET /api/v1/topology/health-matrix` | 200 | PASS |
| topo-06 | POST /ai/chat (show topology) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| topo-07 | POST /ai/chat (navigate topology) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| topo-08 | POST /ai/chat (data flow) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| topo-09 | POST /ai/chat (health matrix) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| topo-10 | GET /ai/suggestions (topology) | GET | `GET /api/v1/ai/suggestions?route=/topology` | 200 | PASS |

## Phase: GAP_PHASE2 (12/15 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| gp2-01 | GET /health/full (G28) | GET | `GET /health/full` | 200 | PASS |
| gp2-02 | /health/full has checks key | GET | `GET /health/full` | 200 | PASS |
| gp2-03 | /health/full has postgres check | GET | `GET /health/full` | 200 | PASS |
| gp2-04 | GET /ready (Redis check, G26) | GET | `GET /ready` | 200 | PASS |
| gp2-05 | POST /profile rejects empty body (G25) | POST | `POST /api/v1/profile` | 404 | **FAIL** |
| gp2-06 | POST /risk-score accepts valid body (G25) | POST | `POST /api/v1/risk-score` | 404 | **FAIL** |
| gp2-07 | POST /ai/chat accepts valid body (G25) | POST | `POST /api/v1/ai/chat` | 200 | PASS |
| gp2-08 | POST /policies/ triggers NATS (G30) | POST | `POST /api/v1/policies/` | 201 | PASS |
| gp2-09 | DELETE /policies/{id} triggers NATS (G30) | DELETE | `DELETE /api/v1/policies/ec613bc0-658d-4101-84b6-79505fdea797` | 204 | PASS |
| gp2-10 | GET /health passes with OTel middleware (G35) | GET | `GET /health` | 200 | PASS |
| gp2-11 | GET /health returns X-Request-ID (G39) | GET | `GET /health` | 200 | PASS |
| gp2-12 | GET /health/full has pool stats (G36) | GET | `GET /health/full` | 200 | PASS |
| gp2-13 | POST /auth/logout (G24) | POST | `POST /api/v1/auth/logout` | 200 | PASS |
| gp2-14 | GET / (React ErrorBoundary, G34) | GET | `GET /` | 404 | **FAIL** |
| gp2-15 | GET /health (Docker Compose, G13/G40) | GET | `GET /health` | 200 | PASS |

## Phase: HYBRID (31/35 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| hyb-01 | GET /config/ui | GET | `GET /api/v1/config/ui` | 200 | PASS |
| hyb-02 | GET /config/ui returns deployment fields | GET | `GET /api/v1/config/ui` | 200 | PASS |
| hyb-03 | GET /config/ui returns legacy_nac_enabled field | GET | `GET /api/v1/config/ui` | 200 | PASS |
| hyb-04 | GET /sites/ | GET | `GET /api/v1/sites/` | 200 | PASS |
| hyb-05 | POST /sites/ (create peer site) | POST | `POST /api/v1/sites/` | 201 | PASS |
| hyb-06 | GET /sites/{id} | GET | `GET /api/v1/sites/d8a9c2ef-f7ae-4b3a-a78a-dbae4f7aef35` | 200 | PASS |
| hyb-07 | GET /sites/peer/status | GET | `GET /api/v1/sites/peer/status` | 200 | PASS |
| hyb-08 | DELETE /sites/{id} | DELETE | `DELETE /api/v1/sites/d8a9c2ef-f7ae-4b3a-a78a-dbae4f7aef35` | 200 | PASS |
| hyb-09 | GET /connectors/ | GET | `GET /api/v1/connectors/` | 200 | PASS |
| hyb-10 | POST /connectors/register | POST | `POST /api/v1/connectors/register` | 201 | PASS |
| hyb-11 | POST /connectors/{id}/heartbeat | POST | `POST /api/v1/connectors/c4b9d0d9-25f1-45d2-853d-8e18b6c49cb1/heartbeat` | 200 | PASS |
| hyb-12 | GET /connectors/{id} | GET | `GET /api/v1/connectors/c4b9d0d9-25f1-45d2-853d-8e18b6c49cb1` | 200 | PASS |
| hyb-13 | DELETE /connectors/{id} | DELETE | `DELETE /api/v1/connectors/c4b9d0d9-25f1-45d2-853d-8e18b6c49cb1` | 200 | PASS |
| hyb-14 | GET /nodes/ (registry) | GET | `GET /api/v1/nodes/` | 200 | PASS |
| hyb-15 | POST /nodes/register | POST | `POST /api/v1/nodes/register` | 201 | PASS |
| hyb-16 | POST /nodes/{id}/heartbeat | POST | `POST /api/v1/nodes/bff294bd-03e2-4c27-8307-62263c3aae00/heartbeat` | 200 | PASS |
| hyb-17 | POST /nodes/{id}/drain | POST | `POST /api/v1/nodes/bff294bd-03e2-4c27-8307-62263c3aae00/drain` | 200 | PASS |
| hyb-18 | DELETE /nodes/{id} | DELETE | `DELETE /api/v1/nodes/bff294bd-03e2-4c27-8307-62263c3aae00` | 200 | PASS |
| hyb-19 | GET /health with X-NeuraNAC-Site: local | GET | `GET /api/v1/health` | 200 | PASS |
| hyb-20 | GET /health with X-NeuraNAC-Site: all | GET | `GET /api/v1/health` | 200 | PASS |
| hyb-21 | V004 neuranac_sites table exists | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| hyb-22 | V004 neuranac_connectors table exists | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| hyb-23 | V004 neuranac_node_registry table exists | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| hyb-24 | V004 neuranac_deployment_config table exists | GET | `GET /api/v1/diagnostics/db-schema-check` | 200 | PASS |
| hyb-25 | Default site in neuranac_sites | GET | `GET /api/v1/sites/` | 200 | PASS |
| hyb-26 | GET /nodes/twin-status (legacy fallback) | GET | `GET /api/v1/nodes/twin-status` | 200 | PASS |
| hyb-27 | GET /nodes/sync-status (legacy fallback) | GET | `GET /api/v1/nodes/sync-status` | 200 | PASS |
| hyb-28 | AI intent: list sites | POST | `POST http://localhost:8081/api/v1/chat` | 0 | **FAIL** |
| hyb-29 | AI intent: peer status | POST | `POST http://localhost:8081/api/v1/chat` | 0 | **FAIL** |
| hyb-30 | AI intent: list connectors | POST | `POST http://localhost:8081/api/v1/chat` | 0 | **FAIL** |
| hyb-31 | GET /sites (SiteManagementPage) | GET | `GET http://localhost:5173/sites` | 0 | **FAIL** |
| hyb-32 | Bridge Connector Dockerfile exists | GET | `GET /api/v1/health` | 200 | PASS |
| hyb-33 | Helm values-onprem-hybrid.yaml parseable | GET | `GET /api/v1/health` | 200 | PASS |
| hyb-34 | Helm values-cloud-hybrid.yaml parseable | GET | `GET /api/v1/health` | 200 | PASS |
| hyb-35 | K8s CRD neuranac-node.yaml has siteId field | GET | `GET /api/v1/health` | 200 | PASS |

## Phase: SCENARIO_S1 (7/8 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| s1-01 | Health shows hybrid mode | GET | `GET /health` | 200 | PASS |
| s1-02 | UI config: deploymentMode=hybrid, legacyNacEnabled=true | GET | `GET /api/v1/config/ui` | 200 | PASS |
| s1-03 | Sites: at least 1 site registered | GET | `GET /api/v1/sites/` | 200 | PASS |
| s1-04 | Connectors endpoint available | GET | `GET /api/v1/connectors/` | 200 | PASS |
| s1-05 | NeuraNAC summary accessible | GET | `GET /api/v1/legacy-nac/summary` | 200 | PASS |
| s1-06 | Federation peer status reachable | GET | `GET /api/v1/sites/peer/status` | 200 | PASS |
| s1-07 | Policy engine health includes site_id | GET | `GET http://localhost:8082/health` | 0 | **FAIL** |
| s1-08 | Node registry available | GET | `GET /api/v1/nodes/` | 200 | PASS |

## Phase: SCENARIO_S2 (6/6 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| s2-01 | Health shows standalone mode | GET | `GET /health` | 200 | PASS |
| s2-02 | UI config: deploymentMode=standalone, legacyNacEnabled=false | GET | `GET /api/v1/config/ui` | 200 | PASS |
| s2-03 | bridge connectors returns empty (NeuraNAC disabled) | GET | `GET /api/v1/connectors/` | 200 | PASS |
| s2-04 | Single site in standalone | GET | `GET /api/v1/sites/` | 200 | PASS |
| s2-05 | RADIUS auth still works (no NeuraNAC dep) | GET | `GET /api/v1/sessions/` | 200 | PASS |
| s2-06 | Policies endpoint works standalone | GET | `GET /api/v1/policies/` | 200 | PASS |

## Phase: SCENARIO_S3 (6/6 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| s3-01 | Health shows standalone+onprem | GET | `GET /health` | 200 | PASS |
| s3-02 | UI config: siteType=onprem, legacyNacEnabled=false | GET | `GET /api/v1/config/ui` | 200 | PASS |
| s3-03 | Twin-node sync status accessible | GET | `GET /api/v1/nodes/sync-status` | 200 | PASS |
| s3-04 | Twin-node twin-status accessible | GET | `GET /api/v1/nodes/twin-status` | 200 | PASS |
| s3-05 | NeuraNAC pages disabled (connectors empty) | GET | `GET /api/v1/connectors/` | 200 | PASS |
| s3-06 | Policies endpoint works on-prem | GET | `GET /api/v1/policies/` | 200 | PASS |

## Phase: SCENARIO_S4 (8/8 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| s4-01 | Health shows hybrid mode | GET | `GET /health` | 200 | PASS |
| s4-02 | UI config: deploymentMode=hybrid, legacyNacEnabled=false | GET | `GET /api/v1/config/ui` | 200 | PASS |
| s4-03 | bridge connectors empty (NeuraNAC disabled) | GET | `GET /api/v1/connectors/` | 200 | PASS |
| s4-04 | Federation peer status reachable | GET | `GET /api/v1/sites/peer/status` | 200 | PASS |
| s4-05 | Multiple sites (hybrid pair) | GET | `GET /api/v1/sites/` | 200 | PASS |
| s4-06 | Node registry available | GET | `GET /api/v1/nodes/` | 200 | PASS |
| s4-07 | Sync status for hybrid pair | GET | `GET /api/v1/nodes/sync-status` | 200 | PASS |
| s4-08 | Policies endpoint works hybrid no-NeuraNAC | GET | `GET /api/v1/policies/` | 200 | PASS |

## Phase: INGESTION (20/20 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| ing-01 | GET /telemetry/events | GET | `GET /api/v1/telemetry/events` | 200 | PASS |
| ing-02 | GET /telemetry/events?type=snmp | GET | `GET /api/v1/telemetry/events?event_type=snmp` | 200 | PASS |
| ing-03 | GET /telemetry/events?severity=warning | GET | `GET /api/v1/telemetry/events?severity=warning` | 200 | PASS |
| ing-04 | GET /telemetry/events?since_hours=24 | GET | `GET /api/v1/telemetry/events?since_hours=24` | 200 | PASS |
| ing-05 | GET /telemetry/events/summary | GET | `GET /api/v1/telemetry/events/summary` | 200 | PASS |
| ing-06 | GET /telemetry/events/summary?hours=1 | GET | `GET /api/v1/telemetry/events/summary?since_hours=1` | 200 | PASS |
| ing-07 | GET /telemetry/flows | GET | `GET /api/v1/telemetry/flows` | 200 | PASS |
| ing-08 | GET /telemetry/flows?protocol=6 | GET | `GET /api/v1/telemetry/flows?protocol=6` | 200 | PASS |
| ing-09 | GET /telemetry/flows?dst_port=443 | GET | `GET /api/v1/telemetry/flows?dst_port=443` | 200 | PASS |
| ing-10 | GET /telemetry/flows/top-talkers | GET | `GET /api/v1/telemetry/flows/top-talkers` | 200 | PASS |
| ing-11 | GET /telemetry/flows/top-talkers?hours=1 | GET | `GET /api/v1/telemetry/flows/top-talkers?since_hours=1&limit=5` | 200 | PASS |
| ing-12 | GET /telemetry/dhcp | GET | `GET /api/v1/telemetry/dhcp` | 200 | PASS |
| ing-13 | GET /telemetry/dhcp?hostname=laptop | GET | `GET /api/v1/telemetry/dhcp?hostname=laptop` | 200 | PASS |
| ing-14 | GET /telemetry/dhcp?os_guess=Windows | GET | `GET /api/v1/telemetry/dhcp?os_guess=Windows` | 200 | PASS |
| ing-15 | GET /telemetry/dhcp/os-distribution | GET | `GET /api/v1/telemetry/dhcp/os-distribution` | 200 | PASS |
| ing-16 | GET /telemetry/neighbors | GET | `GET /api/v1/telemetry/neighbors` | 200 | PASS |
| ing-17 | GET /telemetry/neighbors?protocol=cdp | GET | `GET /api/v1/telemetry/neighbors?protocol=cdp` | 200 | PASS |
| ing-18 | GET /telemetry/neighbors/topology-map | GET | `GET /api/v1/telemetry/neighbors/topology-map` | 200 | PASS |
| ing-19 | GET /telemetry/collectors | GET | `GET /api/v1/telemetry/collectors` | 200 | PASS |
| ing-20 | GET /telemetry/health | GET | `GET /api/v1/telemetry/health` | 200 | PASS |

## Phase: MISSED_ITEMS (17/17 passed)

| # | Test | Method | Endpoint | HTTP | Status |
|---|------|--------|----------|------|--------|
| mi-01 | GET /audit/ (list) | GET | `GET /api/v1/audit/` | 200 | PASS |
| mi-02 | POST /audit/ (create entry) | POST | `POST /api/v1/audit/` | 422 | PASS |
| mi-03 | GET /audit/verify-chain | GET | `GET /api/v1/audit/verify-chain` | 200 | PASS |
| mi-04 | POST /audit/backfill-hashes | POST | `POST /api/v1/audit/backfill-hashes` | 200 | PASS |
| mi-05 | GET /feature-flags/ | GET | `GET /api/v1/feature-flags/` | 200 | PASS |
| mi-06 | POST /feature-flags/ | POST | `POST /api/v1/feature-flags/` | 409 | PASS |
| mi-07 | GET /feature-flags/{name}/status | GET | `GET /api/v1/feature-flags/sanity_test_flag/status` | 404 | PASS |
| mi-08 | PUT /feature-flags/{id} | PUT | `PUT /api/v1/feature-flags/ca8f0466-3fa1-40f3-8ccb-3502f8475758` | 404 | PASS |
| mi-09 | GET /ai/agents/ | GET | `GET /api/v1/ai/agents/` | 200 | PASS |
| mi-10 | POST /ai/agents/ (create) | POST | `POST /api/v1/ai/agents/` | 201 | PASS |
| mi-11 | GET /ai/agents/{id}/delegation-chain | GET | `GET /api/v1/ai/agents/217f9d6f-3ae1-4304-9744-8f9a334f12b9/delegation-chain` | 200 | PASS |
| mi-12 | POST /ai/agents/{id}/check-scope | POST | `POST /api/v1/ai/agents/217f9d6f-3ae1-4304-9744-8f9a334f12b9/check-scope?action=ai:read` | 200 | PASS |
| mi-13 | POST /ai/agents/{id}/revoke | POST | `POST /api/v1/ai/agents/217f9d6f-3ae1-4304-9744-8f9a334f12b9/revoke` | 200 | PASS |
| mi-14 | DELETE /ai/agents/{id} | DELETE | `DELETE /api/v1/ai/agents/217f9d6f-3ae1-4304-9744-8f9a334f12b9` | 204 | PASS |
| mi-15 | GET /ai/models (registry) | GET | `GET /api/v1/ai/models` | 200 | PASS |
| mi-16 | GET /ai/tls/detections | GET | `GET /api/v1/ai/tls/detections` | 200 | PASS |
| mi-17 | GET /ai/tls/stats | GET | `GET /api/v1/ai/tls/stats` | 200 | PASS |

## Failed Tests Detail

### aid-09
- **Endpoint:** `POST /api/v1/ai/chat`
- **HTTP Code:** 404
- **Response:** `{"detail":"Not Found"}`

### aid-10
- **Endpoint:** `GET /api/v1/ai/capabilities`
- **HTTP Code:** 404
- **Response:** `{"detail":"Not Found"}`

### aid-12
- **Endpoint:** `POST /api/v1/training/train`
- **HTTP Code:** 404
- **Response:** `{"detail":"Not Found"}`

### gap-p0-06
- **Endpoint:** `POST /api/v1/profile`
- **HTTP Code:** 422
- **Response:** `{"detail":[{"type":"missing","loc":["body"],"msg":"Field required","input":null,"url":"https://errors.pydantic.dev/2.6/v/missing"}]}`

### gp2-05
- **Endpoint:** `POST /api/v1/profile`
- **HTTP Code:** 404
- **Response:** `{"detail":"Not Found"}`

### gp2-06
- **Endpoint:** `POST /api/v1/risk-score`
- **HTTP Code:** 404
- **Response:** `{"detail":"Not Found"}`

### gp2-14
- **Endpoint:** `GET /`
- **HTTP Code:** 404
- **Response:** `{"detail":"Not Found"}`

### hyb-28
- **Endpoint:** `POST http://localhost:8081/api/v1/chat`
- **HTTP Code:** 0

### hyb-29
- **Endpoint:** `POST http://localhost:8081/api/v1/chat`
- **HTTP Code:** 0

### hyb-30
- **Endpoint:** `POST http://localhost:8081/api/v1/chat`
- **HTTP Code:** 0

### hyb-31
- **Endpoint:** `GET http://localhost:5173/sites`
- **HTTP Code:** 0

### s1-07
- **Endpoint:** `GET http://localhost:8082/health`
- **HTTP Code:** 0

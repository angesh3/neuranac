# NeuraNAC Sanity Test — Bug Fixes & Validation Summary

**Date:** 2026-02-27  
**Final Result:** 211/211 tests passing (100%)

## Progression

| Run | Pass | Fail | Skip | Notes                                                        |
| --- | ---- | ---- | ---- | ------------------------------------------------------------ |
| 1   | 157  | 32   | 22   | Initial run — many payload, backend, and cascade failures    |
| 2   | 205  | 5    | 1    | Fixed 20+ payload schemas, 3 missing DB tables, 3 route bugs |
| 3   | 210  | 1    | 0    | Fixed route shadows, FK violations, missing required fields  |
| 4   | 211  | 0    | 0    | Fixed last `policy_sets.id` NOT NULL violation               |

## Backend Bugs Fixed

### 1. `legacy_nac_enhanced.py` — AmbiguousParameterError in wizard step execution (P23)
- **Root cause:** SQL `CASE WHEN :st = 'completed' THEN NOW() END` reused `:st` parameter, causing SQLAlchemy bind ambiguity.
- **Fix:** Compute `completed_at` in Python before the SQL query, use separate `:ca` param.

### 2. `legacy_nac_enhanced.py` — AmbiguousParameterError in schedule PUT (P18)
- **Root cause:** `next_run_at` calculation reused `:iv` (interval_minutes) inline.
- **Fix:** Compute `next_run` in Python, bind as `:nr`.

### 3. `legacy_nac_enhanced.py` — NOT NULL violation in apply_translated_policy (P20)
- **Root cause:** `INSERT INTO policy_sets` omitted `id` column; table has no default UUID generator.
- **Fix:** Added `gen_random_uuid()` for the `id` column in the INSERT.

### 4. `certificates.py` — TypeError on certificate creation
- **Root cause:** Code used `certificate_pem=` but the model column is `cert_pem`.
- **Fix:** Renamed to `cert_pem=`.

### 5. `audit.py` — Route shadowing on `/verify-chain`
- **Root cause:** `GET /{log_id}` registered before `GET /verify-chain`, so FastAPI matched "verify-chain" as a `log_id` UUID (422).
- **Fix:** Moved `/{log_id}` route after all specific `/verify-chain`, `/reports/summary`, `/reports/auth` routes.

### 6. `webhooks.py` — Route shadowing on `/plugins`
- **Root cause:** `GET /{webhook_id}` registered before `GET /plugins`, so "plugins" matched as a webhook_id (404).
- **Fix:** Moved all `/plugins` routes before `/{webhook_id}` routes.

## Missing Database Columns/Tables Created

| Table                | Column/Action             | Reason                                   |
| -------------------- | ------------------------- | ---------------------------------------- |
| `internal_users`     | Created table             | Guest account endpoints depend on it     |
| `byod_registrations` | Created table             | BYOD registration endpoint depends on it |
| `posture_results`    | Created table             | Posture results endpoint depends on it   |
| `policy_sets`        | Added `match_type` column | legacy policy translation apply needs it    |
| `policy_sets`        | Added `is_active` column  | legacy policy translation apply needs it    |

## Test Payload Fixes (422 errors)

| Test ID  | Endpoint                            | Issue                         | Fix                                                            |
| -------- | ----------------------------------- | ----------------------------- | -------------------------------------------------------------- |
| ai-02    | POST /ai/agents/                    | Missing `agent_name` field    | Changed `name` → `agent_name`                                  |
| seg-04   | PUT /segmentation/sgts/{id}         | Missing required `tag_value`  | Added `tag_value: 9999`                                        |
| siem-05  | POST /siem/forward                  | Wrong field names             | Used `severity` + `details` per `ForwardEventRequest` schema   |
| siem-07  | POST /siem/soar/playbooks           | Wrong field names             | Used `trigger_event` + `webhook_url` per `SOARPlaybook` schema |
| wh-04    | PUT /webhooks/{id}                  | Missing required fields       | Added `url` + `events` per `WebhookCreate` schema              |
| wh-08    | POST /webhooks/plugins              | Wrong field names             | Used `version` + `description` per `PluginRegister` schema     |
| priv-02  | POST /privacy/subjects              | Wrong field names             | Used `subject_type` + `subject_identifier` per schema          |
| priv-06  | POST /privacy/consent               | FK violation + missing fields | Used created `subject_id`, added `legal_basis`                 |
| priv-09  | POST /privacy/exports               | FK violation + wrong fields   | Used created `subject_id`, used `requested_by`                 |
| guest-06 | POST /guest/accounts                | Extra fields                  | Simplified to `username` only                                  |
| guest-10 | POST /captive-portal/authenticate   | Wrong fields                  | Used `client_mac`, `client_ip`, `user_agent`                   |
| guest-11 | POST /guest/byod/register           | Wrong fields                  | Used `endpoint_mac`, `user_id`, `device_name`                  |
| post-05  | POST /posture/assess                | Wrong fields                  | Used `endpoint_mac` + `checks` array                           |
| lnacv-13  | POST /policies/translate            | Wrong field                   | Changed `policy_id` → `policy_name`                    |
| setup-03 | POST /setup/network-scan            | Wrong field                   | Changed `subnets` array → `subnet` string                      |
| setup-04 | POST /setup/identity-source         | Wrong structure               | Wrapped name in `config` object                                |
| setup-06 | POST /setup/network-design/generate | Missing body                  | Added `description` field                                      |
| net-06   | POST /network-devices/discover      | Timeout on large subnet       | Changed to `127.0.0.0/30`                                      |

## Sanity Runner Enhancements

- **Body placeholder resolution:** Added `resolve_body()` to substitute `{resource_key}` in request body values (not just URL paths), enabling FK-dependent test chains.
- **Python 3.9 compatibility:** Replaced `X | None` type hints with `Optional[X]`.
- **Configurable delay:** Request delay passed as parameter, not global.

## Validated API Phases (211 endpoints)

| Phase            | Tests   | Status      |
| ---------------- | ------- | ----------- |
| Infrastructure   | 4       | ✅ 100%     |
| Authentication   | 3       | ✅ 100%     |
| Policies         | 11      | ✅ 100%     |
| Identity Sources | 11      | ✅ 100%     |
| Network Devices  | 6       | ✅ 100%     |
| Endpoints        | 7       | ✅ 100%     |
| Segmentation     | 6       | ✅ 100%     |
| Certificates     | 6       | ✅ 100%     |
| Sessions         | 2       | ✅ 100%     |
| Guest Access     | 12      | ✅ 100%     |
| Posture          | 6       | ✅ 100%     |
| SIEM             | 8       | ✅ 100%     |
| Webhooks         | 11      | ✅ 100%     |
| Privacy          | 9       | ✅ 100%     |
| AI Agents        | 10      | ✅ 100%     |
| Audit            | 4       | ✅ 100%     |
| Diagnostics      | 5       | ✅ 100%     |
| Licenses         | 4       | ✅ 100%     |
| Nodes            | 4       | ✅ 100%     |
| Setup            | 7       | ✅ 100%     |
| NeuraNAC Core         | 14      | ✅ 100%     |
| NeuraNAC Enhanced     | 35      | ✅ 100%     |
| Web Dashboard    | 26      | ✅ 100%     |
| **Total**        | **211** | **✅ 100%** |

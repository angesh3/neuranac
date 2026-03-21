-- NeuraNAC Seed Data - Default configuration for development/demo

-- Ensure default tenant exists (bootstrap.py also creates this, but seed needs it for FK references)
INSERT INTO tenants (name, slug, status) VALUES ('Default', 'default', 'active')
ON CONFLICT (slug) DO NOTHING;

-- Built-in RADIUS dictionaries
INSERT INTO radius_dictionaries (vendor, name, attributes, is_builtin) VALUES
('IETF', 'RFC 2865 - RADIUS', '{"User-Name":1,"User-Password":2,"NAS-IP-Address":4,"NAS-Port":5,"Service-Type":6,"Framed-Protocol":7,"Framed-IP-Address":8,"Filter-Id":11,"Reply-Message":18,"State":24,"Vendor-Specific":26,"Session-Timeout":27,"Idle-Timeout":28,"Called-Station-Id":30,"Calling-Station-Id":31,"NAS-Identifier":32,"Acct-Status-Type":40,"Acct-Session-Id":44,"NAS-Port-Type":61,"Tunnel-Type":64,"Tunnel-Medium-Type":65,"Tunnel-Private-Group-ID":81,"EAP-Message":79,"Message-Authenticator":80}', true),
('Cisco', 'Cisco IOS/NeuraNAC', '{"Cisco-AV-Pair":1,"Cisco-NAS-Port":2,"Cisco-Disconnect-Cause":195,"Cisco-SGT":254}', true),
('Aruba', 'Aruba ClearPass', '{"Aruba-User-Role":1,"Aruba-User-VLAN":2,"Aruba-AP-Group":5}', true),
('Juniper', 'Juniper EX/SRX', '{"Juniper-Local-User-Name":1,"Juniper-Allow-Commands":2,"Juniper-Deny-Commands":3}', true),
('Microsoft', 'Microsoft NPS', '{"MS-MPPE-Send-Key":16,"MS-MPPE-Recv-Key":17,"MS-CHAP-Response":1,"MS-CHAP2-Response":25}', true),
('Meraki', 'Cisco Meraki', '{"Meraki-Device-Name":1,"Meraki-Network-Name":2}', true);

-- Built-in AI service signatures
INSERT INTO ai_services (name, category, dns_patterns, sni_patterns, risk_level, is_approved, is_builtin) VALUES
('OpenAI ChatGPT', 'llm', '["api.openai.com","chat.openai.com"]', '["api.openai.com"]', 'high', false, true),
('Anthropic Claude', 'llm', '["api.anthropic.com","claude.ai"]', '["api.anthropic.com"]', 'high', false, true),
('Google Gemini', 'llm', '["generativelanguage.googleapis.com","gemini.google.com"]', '[]', 'high', false, true),
('GitHub Copilot', 'coding', '["copilot.github.com","api.githubcopilot.com"]', '[]', 'medium', false, true),
('Hugging Face', 'ml_platform', '["huggingface.co","api-inference.huggingface.co"]', '[]', 'medium', false, true),
('Replicate', 'ml_platform', '["api.replicate.com"]', '[]', 'medium', false, true),
('Midjourney', 'image_gen', '["midjourney.com"]', '[]', 'medium', false, true),
('Stability AI', 'image_gen', '["api.stability.ai"]', '[]', 'medium', false, true),
('Cohere', 'llm', '["api.cohere.ai"]', '[]', 'medium', false, true),
('AWS Bedrock', 'cloud_ai', '["bedrock-runtime.amazonaws.com"]', '[]', 'low', true, true),
('Azure OpenAI', 'cloud_ai', '["openai.azure.com"]', '[]', 'low', true, true);

-- Built-in endpoint profiles
INSERT INTO endpoint_profiles (name, match_rules, device_type, vendor, is_builtin) VALUES
('Windows PC', '[{"field":"dhcp.hostname","operator":"matches","value":"^DESKTOP-.*"},{"field":"dhcp.options","operator":"contains","value":"MSFT"}]', 'windows-pc', 'Microsoft', true),
('macOS', '[{"field":"oui.vendor","operator":"equals","value":"Apple"},{"field":"dhcp.hostname","operator":"matches","value":"^[A-Z].*MacBook.*"}]', 'macos', 'Apple', true),
('iPhone', '[{"field":"oui.vendor","operator":"equals","value":"Apple"},{"field":"dhcp.hostname","operator":"matches","value":".*iPhone.*"}]', 'iphone', 'Apple', true),
('Android', '[{"field":"dhcp.vendor_class","operator":"contains","value":"android"}]', 'android', 'Various', true),
('IP Phone', '[{"field":"lldp.system_description","operator":"contains","value":"Cisco IP Phone"}]', 'ip-phone', 'Cisco', true),
('Printer', '[{"field":"port","operator":"in","value":"9100,631,515"},{"field":"dhcp.hostname","operator":"matches","value":".*[Pp]rint.*"}]', 'printer', 'Various', true),
('IP Camera', '[{"field":"port","operator":"in","value":"554,8554,80"},{"field":"oui.vendor","operator":"in","value":"Hikvision,Dahua,Axis"}]', 'camera', 'Various', true),
('IoT Sensor', '[{"field":"oui.vendor","operator":"in","value":"Raspberry Pi,Espressif,Texas Instruments"}]', 'iot-sensor', 'Various', true),
('AI GPU Node', '[{"field":"port","operator":"in","value":"11434,8000,5000"},{"field":"dns","operator":"matches","value":".*\\.(openai|anthropic|huggingface)\\..*"}]', 'ai-gpu-node', 'Various', true);

-- Default test NAD (for radtest from localhost)
INSERT INTO network_devices (tenant_id, name, ip_address, device_type, vendor, model, shared_secret_encrypted, status)
SELECT t.id, 'localhost-test', '127.0.0.1', 'virtual', 'Test', 'radtest', 'testing123', 'active'
FROM tenants t WHERE t.slug = 'default'
ON CONFLICT DO NOTHING;

INSERT INTO network_devices (tenant_id, name, ip_address, device_type, vendor, model, shared_secret_encrypted, status)
SELECT t.id, 'docker-host', '172.17.0.1', 'virtual', 'Test', 'radtest', 'testing123', 'active'
FROM tenants t WHERE t.slug = 'default'
ON CONFLICT DO NOTHING;

-- Default test user for radtest (plaintext password for dev, bcrypt in production)
INSERT INTO internal_users (tenant_id, username, password_hash, email, groups, status)
SELECT t.id, 'testuser', 'testing123', 'testuser@neuranac.local', '["employees"]', 'active'
FROM tenants t WHERE t.slug = 'default'
ON CONFLICT DO NOTHING;

INSERT INTO internal_users (tenant_id, username, password_hash, email, groups, status)
SELECT t.id, 'admin', 'admin123', 'admin@neuranac.local', '["admins"]', 'active'
FROM tenants t WHERE t.slug = 'default'
ON CONFLICT DO NOTHING;

-- Default feature flags
INSERT INTO feature_flags (name, enabled, description) VALUES
('ai_shadow_detection', true, 'Enable Shadow AI traffic detection'),
('ai_nlp_policy', true, 'Enable NLP policy translation'),
('ai_risk_scoring', true, 'Enable AI-powered risk scoring'),
('ai_troubleshooter', true, 'Enable AI troubleshooting assistant'),
('ml_profiling', false, 'Enable ML-based endpoint profiling (requires ONNX model)'),
('twin_node_sync', true, 'Enable twin-node synchronization'),
('auto_coa', true, 'Enable automatic CoA on policy changes'),
('guest_portal', true, 'Enable guest portal'),
('byod_onboarding', true, 'Enable BYOD self-registration'),
('posture_assessment', true, 'Enable posture compliance checking'),
('fips_mode', false, 'Enable FIPS 140-3 compliant cryptography'),
('audit_chain', true, 'Enable tamper-proof audit log chain'),
('auto_cert_renewal', true, 'Auto-renew certificates before expiry');

-- Built-in threat signatures
INSERT INTO ai_threat_signatures (name, threat_type, indicators, severity, source) VALUES
('Credential Stuffing Bot', 'credential_attack', '{"pattern":"rapid_auth_failures","threshold":10,"window_minutes":5}', 'high', 'builtin'),
('AI Agent Impersonation', 'identity_spoofing', '{"pattern":"ai_agent_anomalous_behavior","indicators":["unexpected_delegation","scope_escalation"]}', 'critical', 'builtin'),
('Data Exfiltration via AI', 'data_leak', '{"pattern":"high_volume_ai_upload","threshold_mb":500,"window_hours":1}', 'critical', 'builtin'),
('Shadow LLM Local', 'shadow_ai', '{"pattern":"local_llm_detection","ports":[11434,8000],"process_names":["ollama","vllm"]}', 'medium', 'builtin'),
('Adversarial ML Attack', 'adversarial', '{"pattern":"model_poisoning_attempt","indicators":["malformed_input","gradient_leak"]}', 'high', 'builtin'),
('Autonomous Agent Swarm', 'autonomous_attack', '{"pattern":"rapid_agent_delegation","max_depth":5,"window_minutes":10}', 'critical', 'builtin');

-- ─── Default site + deployment config (V004 hybrid architecture) ────────────

INSERT INTO neuranac_sites (id, tenant_id, name, site_type, deployment_mode, api_url, status)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000000',
    'Local Site',
    'onprem',
    'standalone',
    'http://localhost:8080',
    'active'
) ON CONFLICT DO NOTHING;

INSERT INTO neuranac_deployment_config (tenant_id, deployment_mode, legacy_nac_enabled, primary_site_id)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'standalone',
    false,
    '00000000-0000-0000-0000-000000000001'
) ON CONFLICT DO NOTHING;

-- Default tenant quota (unlimited for system tenant)
INSERT INTO neuranac_tenant_quotas (tenant_id, tier, max_sites, max_nodes, max_connectors, max_sessions)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'unlimited', 999, 999, 999, 999999
) ON CONFLICT (tenant_id) DO NOTHING;

-- Default data retention policies
INSERT INTO data_retention_policies (tenant_id, data_type, retention_days) VALUES
(NULL, 'sessions', 90),
(NULL, 'audit_logs', 365),
(NULL, 'accounting', 180),
(NULL, 'ai_shadow_detections', 90),
(NULL, 'ai_risk_scores', 30),
(NULL, 'posture_results', 60);

import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Lightbulb, RotateCcw } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface SuggestedQuestion {
  text: string;
  category: string;
}

const suggestedQuestions: SuggestedQuestion[] = [
  { text: 'How do I add a new network switch to NeuraNAC?', category: 'Setup' },
  { text: 'Why is my RADIUS authentication failing?', category: 'Troubleshoot' },
  { text: 'How do I configure EAP-TLS for corporate laptops?', category: 'Authentication' },
  { text: 'What is Shadow AI detection and how does it work?', category: 'AI Features' },
  { text: 'How do I set up guest WiFi access?', category: 'Guest' },
  { text: 'How do I create a policy to assign VLANs?', category: 'Policies' },
  { text: 'What posture checks does NeuraNAC support?', category: 'Posture' },
  { text: 'How do I set up twin-node high availability?', category: 'HA' },
  { text: 'How do I integrate NeuraNAC with Splunk SIEM?', category: 'Integration' },
  { text: 'What NAD vendors does NeuraNAC support?', category: 'Compatibility' },
  { text: 'How do I configure SAML SSO with Okta?', category: 'Identity' },
  { text: 'How do I check if all services are healthy?', category: 'Troubleshoot' },
];

const knowledgeBase: Record<string, string> = {
  'add.*switch|add.*device|add.*nad|register.*device|new.*switch': `To add a new network device (NAD) to NeuraNAC:

**Via Dashboard:**
1. Navigate to **Network Devices** in the sidebar
2. Click **Add Device**
3. Fill in: Name, IP Address, Device Type, Vendor, Shared Secret
4. Set CoA Port (default 3799) and RadSec if needed
5. Click **Save**

**Via API:**
\`\`\`
POST /api/v1/network-devices/
{
  "name": "access-switch-01",
  "ip_address": "10.10.1.1",
  "device_type": "switch",
  "vendor": "cisco",
  "shared_secret": "YourSecret123!"
}
\`\`\`

**Then configure the switch:**
\`\`\`
radius server NeuraNAC
  address ipv4 <NeuraNAC_IP> auth-port 1812 acct-port 1813
  key YourSecret123!
dot1x system-auth-control
\`\`\`

💡 **Tip:** Use auto-discovery to find devices on a subnet: POST /api/v1/network-devices/discover`,

  'radius.*fail|auth.*fail|access.reject|reject|not authenticating': `**Debugging RADIUS Authentication Failures:**

**Step 1: Check RADIUS server logs**
\`\`\`
docker logs neuranac-radius | grep -i "auth"
\`\`\`

**Step 2: Verify NAD is registered**
- Dashboard → Network Devices → confirm the NAD IP exists
- Check that the shared secret matches exactly on both sides

**Step 3: Test with radtest**
\`\`\`
radtest testuser testing123 <NeuraNAC_IP> 0 <shared_secret>
\`\`\`

**Step 4: Check policy**
- Dashboard → Policies → ensure a matching policy exists
- Default policy should exist for basic auth

**Common causes:**
- ❌ Shared secret mismatch (most common!)
- ❌ NAD IP not registered in NeuraNAC
- ❌ No matching policy for the request
- ❌ User not found in identity source
- ❌ Account locked due to failed attempts
- ❌ Firewall blocking UDP 1812

**Step 5: Use AI Troubleshooter**
\`\`\`
POST http://localhost:8081/api/v1/troubleshoot
{ "username": "jdoe", "nas_ip": "10.0.0.1", "error": "Access-Reject" }
\`\`\``,

  'eap.tls|certificate.*auth|cert.*based|machine.*cert': `**Configuring EAP-TLS (Certificate-Based Authentication):**

**Prerequisites:**
1. Certificate Authority (CA) configured in NeuraNAC
2. Client certificates deployed to endpoints
3. Server certificate for RADIUS

**Step 1: Import CA Certificate**
Dashboard → Certificates → Import CA → Upload your root CA cert

**Step 2: Generate RADIUS Server Certificate**
\`\`\`
POST /api/v1/certificates/generate
{
  "ca_id": "<ca-uuid>",
  "subject": "CN=radius.neuranac.example.com",
  "usage": "server",
  "validity_days": 365
}
\`\`\`

**Step 3: Create EAP-TLS Policy**
Dashboard → Policies → Create Policy Set
- Condition: Auth-Type equals "EAP-TLS"
- Result: VLAN 100, SGT 10

**Step 4: Configure NAD**
\`\`\`
interface GigabitEthernet1/0/1
  authentication order dot1x
  dot1x pae authenticator
\`\`\`

**EAP-TLS Flow:**
Endpoint → Switch → NeuraNAC: TLS handshake with mutual cert validation → Policy evaluation → Access-Accept with VLAN/SGT`,

  'shadow.*ai|unauthorized.*ai|detect.*ai|ai.*detection': `**Shadow AI Detection in NeuraNAC:**

NeuraNAC monitors network traffic for unauthorized AI service usage.

**14+ Built-in Signatures:**
- OpenAI (ChatGPT, API) — DNS + HTTP headers
- Anthropic (Claude) — DNS + TLS SNI
- Google AI (Gemini) — DNS patterns
- Hugging Face, Cohere, Stability AI — DNS + API patterns
- GitHub Copilot — DNS + HTTP headers
- Amazon Bedrock, Azure OpenAI — Cloud-specific patterns
- Ollama, LM Studio, LocalAI — Local port scanning

**How to Enable:**
1. Dashboard → AI Data Flow → Create Policy
2. Define approved vs. blocked AI services
3. Set response actions: Alert, Quarantine, or Block

**Response Actions:**
- 🔔 **Alert** — Dashboard notification + SIEM event
- 🔒 **Quarantine** — CoA moves endpoint to restricted VLAN
- 🚫 **Block** — SOAR webhook triggers firewall rule

**Check detections:**
Dashboard → Shadow AI → View detection logs

**API:**
\`\`\`
POST http://localhost:8081/api/v1/shadow
{ "dns_queries": ["api.openai.com"], "http_hosts": ["chat.openai.com"] }
\`\`\``,

  'guest.*access|guest.*wifi|captive.*portal|visitor': `**Setting Up Guest WiFi Access:**

**Step 1: Create Guest Portal**
Dashboard → Guest & BYOD → Create Portal
- Name: "Visitor WiFi"
- Fields: name, email, company
- Self-registration: enabled
- Account expiry: 24 hours

**Step 2: Configure Redirect Policy**
Dashboard → Policies → Create Policy Set
- Condition: No 802.1X AND no MAB match
- Result: Guest VLAN (999) + HTTP redirect to portal

**Step 3: Guest Flow**
1. Guest connects to network
2. Unknown MAC → assigned to Guest VLAN
3. HTTP redirected to captive portal
4. Guest fills registration form
5. Bot detection validates submission
6. Account created with random password + expiry
7. Guest re-authenticates → authorized Guest VLAN

**Step 4: Sponsor Approval (Optional)**
- Enable in portal settings
- Sponsors get email notification
- Access activated after approval

**Security:** Bot detection includes honeypot fields, timing analysis, and header verification.`,

  'policy.*vlan|create.*policy|assign.*vlan|vlan.*assign': `**Creating VLAN Assignment Policies:**

**Via Dashboard:**
1. Navigate to **Policies**
2. Click **Create Policy Set**
3. Configure:
   - Name: "Corporate Access Policy"
   - Priority: 1 (lower = higher priority)
4. Add rules:
   - Rule 1: User-Group contains "employees" → VLAN 100, SGT 10
   - Rule 2: User-Group contains "contractors" → VLAN 200, SGT 20
   - Rule 3: Endpoint-Profile equals "printer" → VLAN 300, SGT 30
   - Default: → VLAN 999 (quarantine)

**Available Operators:**
equals, not_equals, contains, starts_with, ends_with, in, not_in, matches (regex), greater_than, less_than, between, is_true, is_false

**VLAN is assigned via RADIUS attributes:**
- Tunnel-Type = VLAN
- Tunnel-Medium-Type = IEEE-802
- Tunnel-Private-Group-Id = <VLAN number>

**Via NLP (Natural Language):**
\`\`\`
POST http://localhost:8081/api/v1/nlp/translate
{ "text": "Assign employees to VLAN 100 with SGT tag 10" }
\`\`\``,

  'posture.*check|compliance.*check|endpoint.*compliance|posture.*assess': `**NeuraNAC Posture Assessment — 8 Check Types:**

| Check | Description |
|-------|-------------|
| antivirus | AV installed and up-to-date |
| firewall | Host firewall enabled |
| disk_encryption | Full disk encryption (BitLocker/FileVault) |
| os_patch | OS patches within threshold (days) |
| screen_lock | Screen lock timeout configured |
| jailbroken | Jailbreak/root detection |
| certificate | Valid client certificate present |
| agent_version | Posture agent meets minimum version |

**Flow:**
1. Endpoint authenticates → posture-pending VLAN
2. Posture agent reports status
3. NeuraNAC evaluates all checks
4. ✅ Compliant → CoA to production VLAN
5. ❌ Non-compliant → CoA to remediation VLAN

**Create Posture Policy:**
\`\`\`
POST /api/v1/posture/policies
{
  "name": "Corporate Compliance",
  "checks": [
    {"type": "antivirus", "required": true},
    {"type": "firewall", "required": true},
    {"type": "disk_encryption", "required": true}
  ]
}
\`\`\``,

  'twin.*node|high.*avail|ha.*setup|failover|replication': `**Twin-Node High Availability Setup:**

NeuraNAC supports on-prem HA with bidirectional replication.

**Step 1: Deploy Node A**
\`\`\`
helm install neuranac-a helm/neuranac -f values-onprem.yaml \\
  --set global.nodeId=twin-a
\`\`\`

**Step 2: Deploy Node B**
\`\`\`
helm install neuranac-b helm/neuranac -f values-onprem.yaml \\
  --set global.nodeId=twin-b \\
  --set syncEngine.peerAddress=node-a:9090
\`\`\`

**Step 3: Configure Node A peer**
\`\`\`
helm upgrade neuranac-a helm/neuranac \\
  --set syncEngine.peerAddress=node-b:9090
\`\`\`

**Step 4: Verify sync**
\`\`\`
curl http://node-a:9100/sync/status
→ { "peer_connected": true, "pending_outbound": 0 }
\`\`\`

**How it works:**
- Config changes create journal entries in PostgreSQL
- Sync Engine streams entries to peer via gRPC
- Last-writer-wins conflict resolution
- Automatic reconnection on network failure

**NAD config:** Add both nodes as RADIUS servers (primary + secondary)`,

  'splunk|siem|qradar|sentinel|syslog|cef|log.*forward': `**SIEM Integration:**

**Configure SIEM Target:**
\`\`\`
POST /api/v1/siem/targets
{
  "name": "Splunk",
  "host": "splunk.example.com",
  "port": 514,
  "protocol": "tcp",
  "format": "cef",
  "event_types": ["auth.success", "auth.failure", "ai.shadow_detected"]
}
\`\`\`

**Supported Formats:** Syslog (RFC 5424), CEF (Common Event Format)
**Supported Platforms:** Splunk, IBM QRadar, Microsoft Sentinel, Elastic/ELK, ArcSight

**Event Types:**
- auth.success / auth.failure
- policy.decision
- posture.noncompliant
- ai.shadow_detected
- coa.triggered
- audit.action

**Test connectivity:**
\`\`\`
POST /api/v1/siem/targets/{id}/test
\`\`\`

Dashboard → Settings → SIEM Configuration for UI-based setup.`,

  'vendor|supported.*device|compatible|cisco|aruba|juniper': `**Supported NAD Vendors:**

**Full Support (RADIUS + TACACS+ + CoA + 802.1X + MAB):**
- Cisco Catalyst 9000/3000/2960
- Cisco ISR 4000, ASR 1000
- Aruba/HPE CX 6000/8000
- Juniper EX2300/EX3400/EX4300
- Dell PowerSwitch

**RADIUS + CoA + 802.1X (no TACACS+):**
- Cisco Meraki MS/MR
- Cisco WLC 9800/5520
- Fortinet FortiSwitch/FortiGate/FortiAP
- Ruckus ICX, SmartZone
- Extreme x435/x440/x465

**RadSec Support:**
- Cisco Catalyst, ISR, ASR
- Aruba CX
- Juniper EX, QFX

**Generic:** Any device supporting standard RADIUS (RFC 2865) will work for basic authentication.

NeuraNAC sends standard RADIUS attributes — no vendor-specific customization needed for basic functionality.`,

  'saml|sso|okta|azure.*ad|single.*sign': `**SAML SSO Configuration (e.g., Okta):**

**Step 1: Create SAML Identity Source**
\`\`\`
POST /api/v1/identity-sources/
{
  "name": "Okta SSO",
  "type": "saml",
  "config": {
    "entity_id": "https://neuranac.example.com/saml",
    "sso_url": "https://company.okta.com/app/neuranac/sso/saml",
    "certificate": "<IdP signing cert PEM>",
    "attribute_mapping": {
      "email": "user.email",
      "groups": "user.groups"
    }
  }
}
\`\`\`

**Step 2: Configure Okta**
- Add NeuraNAC as a SAML application in Okta
- ACS URL: https://neuranac.example.com/api/v1/identity-sources/{id}/saml/acs
- Entity ID: https://neuranac.example.com/saml

**Step 3: Test**
- GET /api/v1/identity-sources/{id}/saml/login → Redirects to Okta
- User authenticates → Okta POSTs to ACS → JWT issued

Also supports: Azure AD, Google Workspace, OneLogin, PingFederate`,

  'health.*check|service.*status|all.*service|everything.*running': `**Checking Service Health:**

**Quick check all services:**
\`\`\`
curl http://localhost:8080/health        # API Gateway
curl http://localhost:8081/health        # AI Engine
curl http://localhost:8082/health        # Policy Engine
curl http://localhost:9100/health        # Sync Engine
curl http://localhost:8222/healthz       # NATS
\`\`\`

**Full system status:**
\`\`\`
curl http://localhost:8080/api/v1/diagnostics/system-status
\`\`\`

**Container status:**
\`\`\`
docker ps --format "table {{.Names}}\\t{{.Status}}"
\`\`\`

**Expected healthy responses:**
- API Gateway: {"status":"healthy","service":"api-gateway"}
- AI Engine: {"status":"healthy","service":"ai-engine"}
- Policy Engine: {"status":"healthy","service":"policy-engine"}
- Sync Engine: {"status":"healthy","service":"sync-engine"}
- NATS: {"status":"ok"}

**If a service is down:**
1. Check logs: \`docker logs neuranac-<service>\`
2. Check dependencies: PostgreSQL, Redis, NATS must be healthy first
3. Restart: \`docker compose restart <service>\``,
};

function findAnswer(question: string): string {
  const q = question.toLowerCase();
  for (const [pattern, answer] of Object.entries(knowledgeBase)) {
    const regex = new RegExp(pattern, 'i');
    if (regex.test(q)) {
      return answer;
    }
  }
  return `I don't have a specific answer for that question in my knowledge base, but here are some suggestions:

1. **Check the Help Docs** — Navigate to Help → Documentation for comprehensive articles
2. **Use the AI Troubleshooter** — POST to http://localhost:8081/api/v1/troubleshoot with your issue details
3. **Check Service Logs** — \`docker logs neuranac-<service>\` for detailed error information
4. **API Documentation** — Visit http://localhost:8080/api/docs for the full API reference
5. **Review the Docs** — See docs/ARCHITECTURE.md, docs/WORKFLOWS.md, and docs/DEPLOYMENT.md

Try rephrasing your question or ask about:
- Adding network devices
- Authentication methods (PAP, EAP-TLS, PEAP)
- Policy creation and VLAN assignment
- Guest access setup
- Shadow AI detection
- Posture assessment
- SIEM integration
- High availability setup
- Supported NAD vendors`;
}

export default function AIHelpPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    // Simulate AI thinking delay
    await new Promise((resolve) => setTimeout(resolve, 500 + Math.random() * 1000));

    const answer = findAnswer(text);
    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: answer,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, assistantMsg]);
    setIsTyping(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const clearChat = () => {
    setMessages([]);
    inputRef.current?.focus();
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] -m-6">
      {/* Header */}
      <div className="border-b border-border bg-card px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-foreground">NeuraNAC AI Assistant</h1>
            <p className="text-xs text-muted-foreground">Ask anything about NeuraNAC configuration, troubleshooting, or features</p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground border border-border rounded-md hover:bg-accent"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Clear Chat
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="max-w-3xl mx-auto p-6">
            <div className="text-center mb-8 mt-8">
              <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                <Bot className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold text-foreground mb-2">How can I help you?</h2>
              <p className="text-muted-foreground text-sm">
                I can help with NeuraNAC configuration, troubleshooting, NAD setup, policy creation, and more.
              </p>
            </div>

            <div className="mb-6">
              <h3 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                <Lightbulb className="h-4 w-4" />
                Suggested Questions
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {suggestedQuestions.map((sq, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(sq.text)}
                    className="text-left p-3 border border-border rounded-lg hover:bg-accent hover:border-primary/30 transition-colors group"
                  >
                    <span className="text-xs text-primary font-medium">{sq.category}</span>
                    <p className="text-sm text-foreground mt-0.5 group-hover:text-primary">{sq.text}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto p-6 space-y-6">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                {msg.role === 'assistant' && (
                  <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-lg p-4 ${
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-card border border-border'
                  }`}
                >
                  <pre className={`whitespace-pre-wrap font-sans text-sm leading-relaxed ${
                    msg.role === 'user' ? '' : 'text-foreground'
                  }`}>
                    {msg.content}
                  </pre>
                  <p className={`text-xs mt-2 ${
                    msg.role === 'user' ? 'text-primary-foreground/60' : 'text-muted-foreground'
                  }`}>
                    {msg.timestamp.toLocaleTimeString()}
                  </p>
                </div>
                {msg.role === 'user' && (
                  <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center flex-shrink-0 mt-1">
                    <User className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
              </div>
            ))}

            {isTyping && (
              <div className="flex gap-3">
                <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-card border border-border rounded-lg p-4">
                  <div className="flex items-center gap-2 text-muted-foreground text-sm">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Thinking...
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border bg-card p-4">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about NeuraNAC configuration, troubleshooting, policies..."
            className="flex-1 px-4 py-3 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            disabled={isTyping}
          />
          <button
            type="submit"
            disabled={!input.trim() || isTyping}
            className="px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
        <p className="text-center text-xs text-muted-foreground mt-2 max-w-3xl mx-auto">
          AI Assistant uses a built-in knowledge base. For complex issues, use the AI Troubleshooter API or check the full documentation.
        </p>
      </div>
    </div>
  );
}

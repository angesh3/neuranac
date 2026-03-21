import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import {
  Shield, Server, Key, CheckCircle2, Copy, ArrowRight,
  ArrowLeft, Loader2, AlertCircle, Terminal, Wifi
} from 'lucide-react'

type WizardStep = 'select-site' | 'generate-code' | 'install-connector' | 'verify'

interface Site {
  id: string
  name: string
  site_type: string
  status: string
}

interface ActivationCode {
  id: string
  code: string
  site_id: string
  connector_type: string
  status: string
  expires_at: string
  created_at: string
}

interface Connector {
  id: string
  name: string
  status: string
  legacy_nac_hostname: string
  tunnel_status: string
  last_heartbeat: string | null
}

const STEPS: { key: WizardStep; label: string; icon: typeof Shield }[] = [
  { key: 'select-site', label: 'Select Site', icon: Server },
  { key: 'generate-code', label: 'Generate Code', icon: Key },
  { key: 'install-connector', label: 'Install Connector', icon: Terminal },
  { key: 'verify', label: 'Verify Connection', icon: CheckCircle2 },
]

function StepIndicator({ current, steps }: { current: WizardStep; steps: typeof STEPS }) {
  const currentIdx = steps.findIndex((s) => s.key === current)
  return (
    <div className="flex items-center justify-center gap-1 mb-8">
      {steps.map((step, idx) => {
        const Icon = step.icon
        const isActive = idx === currentIdx
        const isDone = idx < currentIdx
        return (
          <div key={step.key} className="flex items-center">
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              isActive
                ? 'bg-primary text-primary-foreground shadow-md'
                : isDone
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                : 'bg-muted text-muted-foreground'
            }`}>
              <Icon className="h-4 w-4" />
              <span className="hidden sm:inline">{step.label}</span>
              <span className="sm:hidden">{idx + 1}</span>
            </div>
            {idx < steps.length - 1 && (
              <ArrowRight className={`h-4 w-4 mx-1 ${idx < currentIdx ? 'text-green-500' : 'text-muted-foreground/40'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function OnPremSetupWizardPage() {
  const queryClient = useQueryClient()
  const [step, setStep] = useState<WizardStep>('select-site')
  const [selectedSiteId, setSelectedSiteId] = useState<string>('')
  const [activationCode, setActivationCode] = useState<ActivationCode | null>(null)
  const [copied, setCopied] = useState(false)
  const [connectorType, setConnectorType] = useState<string>('legacy_nac')

  const sitesQuery = useQuery({
    queryKey: ['sites'],
    queryFn: () => api.get('/sites').then((r) => r.data),
  })

  const connectorsQuery = useQuery({
    queryKey: ['connectors'],
    queryFn: () => api.get('/connectors').then((r) => r.data),
    refetchInterval: step === 'verify' ? 5000 : false,
  })

  const generateCodeMutation = useMutation({
    mutationFn: (payload: { site_id: string; connector_type: string }) =>
      api.post('/connectors/activation-codes', payload).then((r) => r.data),
    onSuccess: (data: ActivationCode) => {
      setActivationCode(data)
      setStep('install-connector')
      queryClient.invalidateQueries({ queryKey: ['activation-codes'] })
    },
  })

  const sites: Site[] = (sitesQuery.data?.items || []).filter(
    (s: Site) => s.site_type === 'onprem' || s.site_type === 'cloud'
  )
  const connectors: Connector[] = connectorsQuery.data?.items || []

  const handleCopyCode = () => {
    if (activationCode) {
      navigator.clipboard.writeText(activationCode.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleCopyDockerCmd = () => {
    if (activationCode) {
      const cmd = `docker run -d --name neuranac-bridge \\
  -e NEURANAC_BRIDGE_ACTIVATION_CODE=${activationCode.code} \\
  -e NEURANAC_BRIDGE_CLOUD_NeuraNAC_API_URL=<CLOUD_API_URL> \\
  -e NEURANAC_BRIDGE_LEGACY_NAC_ENABLED=true \\
  -e NEURANAC_BRIDGE_NeuraNAC_HOSTNAME=<NeuraNAC_HOST> \\
  -e NEURANAC_BRIDGE_NeuraNAC_ERS_USERNAME=<NeuraNAC_USER> \\
  -e NEURANAC_BRIDGE_NeuraNAC_ERS_PASSWORD=<NeuraNAC_PASS> \\
  -p 8090:8090 \\
  neuranac/neuranac-bridge:latest`
      navigator.clipboard.writeText(cmd)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const recentConnector = connectors.find(
    (c) => c.status === 'registering' || c.status === 'connected'
  )

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-2xl font-bold text-foreground flex items-center justify-center gap-2">
          <Shield className="h-6 w-6 text-primary" />
          On-Prem Connector Setup
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Zero-trust activation — connect your on-premises network to NeuraNAC Cloud in minutes
        </p>
      </div>

      <StepIndicator current={step} steps={STEPS} />

      {/* Step 1: Select Site */}
      {step === 'select-site' && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold">Select Target Site</h2>
          <p className="text-sm text-muted-foreground">
            Choose the site this on-prem connector will be associated with.
            The connector will bridge your local NeuraNAC/network to this cloud site.
          </p>

          <div className="space-y-2">
            <label className="text-sm font-medium">Connector Type</label>
            <div className="flex gap-2">
              {['legacy_nac', 'meraki', 'dnac'].map((ct) => (
                <button
                  key={ct}
                  onClick={() => setConnectorType(ct)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all ${
                    connectorType === ct
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:border-primary/50'
                  }`}
                >
                  {ct.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Site</label>
            {sitesQuery.isLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground p-4">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading sites...
              </div>
            ) : sites.length === 0 ? (
              <div className="flex items-center gap-2 text-amber-600 bg-amber-50 dark:bg-amber-900/20 p-4 rounded-lg">
                <AlertCircle className="h-4 w-4" />
                <span className="text-sm">No sites available. Create a site in Site Management first.</span>
              </div>
            ) : (
              <div className="grid gap-2">
                {sites.map((site) => (
                  <button
                    key={site.id}
                    onClick={() => setSelectedSiteId(site.id)}
                    className={`flex items-center justify-between p-4 rounded-lg border text-left transition-all ${
                      selectedSiteId === site.id
                        ? 'border-primary bg-primary/5 ring-2 ring-primary/20'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Server className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="font-medium">{site.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {site.site_type} · {site.status}
                        </p>
                      </div>
                    </div>
                    {selectedSiteId === site.id && (
                      <CheckCircle2 className="h-5 w-5 text-primary" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end pt-4">
            <button
              onClick={() => setStep('generate-code')}
              disabled={!selectedSiteId}
              className="flex items-center gap-2 px-6 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary/90 transition-colors"
            >
              Next <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Generate Activation Code */}
      {step === 'generate-code' && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold">Generate Activation Code</h2>
          <p className="text-sm text-muted-foreground">
            An activation code is a single-use, time-limited credential.
            The on-prem connector uses it to securely register with the cloud — no manual
            API keys, certificates, or complex configuration needed.
          </p>

          <div className="bg-muted/50 rounded-lg p-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Site:</span>
              <span className="font-medium">
                {sites.find((s) => s.id === selectedSiteId)?.name || selectedSiteId}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Connector Type:</span>
              <span className="font-medium uppercase">{connectorType}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Code Validity:</span>
              <span className="font-medium">24 hours (single-use)</span>
            </div>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 text-sm text-blue-700 dark:text-blue-300">
            <div className="flex items-start gap-2">
              <Shield className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <div>
                <strong>Zero-Trust Security:</strong> The code can only be used once and expires after 24 hours.
                The connector uses the code to bootstrap a secure, HMAC-signed communication channel.
                No secrets are exposed in configuration files.
              </div>
            </div>
          </div>

          <div className="flex justify-between pt-4">
            <button
              onClick={() => setStep('select-site')}
              className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>
            <button
              onClick={() =>
                generateCodeMutation.mutate({
                  site_id: selectedSiteId,
                  connector_type: connectorType,
                })
              }
              disabled={generateCodeMutation.isPending}
              className="flex items-center gap-2 px-6 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
            >
              {generateCodeMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Generating...
                </>
              ) : (
                <>
                  <Key className="h-4 w-4" /> Generate Activation Code
                </>
              )}
            </button>
          </div>

          {generateCodeMutation.isError && (
            <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-3 rounded-lg text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              Failed to generate code. Ensure you have admin permissions and the site exists.
            </div>
          )}
        </div>
      )}

      {/* Step 3: Install Connector */}
      {step === 'install-connector' && activationCode && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-6">
          <h2 className="text-lg font-semibold">Install On-Prem Connector</h2>

          {/* Activation Code Display */}
          <div className="bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/20 rounded-xl p-6 text-center space-y-2">
            <p className="text-sm text-muted-foreground">Your Activation Code</p>
            <div className="flex items-center justify-center gap-3">
              <code className="text-3xl font-mono font-bold tracking-widest text-primary">
                {activationCode.code}
              </code>
              <button
                onClick={handleCopyCode}
                className="p-2 rounded-lg hover:bg-primary/10 transition-colors"
                title="Copy code"
              >
                {copied ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                ) : (
                  <Copy className="h-5 w-5 text-muted-foreground" />
                )}
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Expires: {new Date(activationCode.expires_at).toLocaleString()}
            </p>
          </div>

          {/* Docker Install Command */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Terminal className="h-4 w-4" /> Docker Installation
              </h3>
              <button
                onClick={handleCopyDockerCmd}
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                <Copy className="h-3 w-3" /> Copy command
              </button>
            </div>
            <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 text-sm overflow-x-auto font-mono">
{`docker run -d --name neuranac-bridge \\
  -e NEURANAC_BRIDGE_ACTIVATION_CODE=${activationCode.code} \\
  -e NEURANAC_BRIDGE_CLOUD_NeuraNAC_API_URL=<CLOUD_API_URL> \\
  -e NEURANAC_BRIDGE_LEGACY_NAC_ENABLED=true \\
  -e NEURANAC_BRIDGE_NeuraNAC_HOSTNAME=<NeuraNAC_HOST> \\
  -e NEURANAC_BRIDGE_NeuraNAC_ERS_USERNAME=<NeuraNAC_USER> \\
  -e NEURANAC_BRIDGE_NeuraNAC_ERS_PASSWORD=<NeuraNAC_PASS> \\
  -p 8090:8090 \\
  neuranac/neuranac-bridge:latest`}
            </pre>
            <p className="text-xs text-muted-foreground">
              Replace <code>&lt;CLOUD_API_URL&gt;</code>, <code>&lt;NeuraNAC_HOST&gt;</code>,
              <code>&lt;NeuraNAC_USER&gt;</code>, and <code>&lt;NeuraNAC_PASS&gt;</code> with your actual values.
              The activation code handles all cloud registration automatically.
            </p>
          </div>

          {/* Helm Install */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Terminal className="h-4 w-4" /> Kubernetes (Helm)
            </h3>
            <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 text-sm overflow-x-auto font-mono">
{`helm install neuranac-connector ./deploy/helm \\
  --set lnacConnector.enabled=true \\
  --set lnacConnector.activationCode=${activationCode.code} \\
  --set lnacConnector.cloudApiUrl=<CLOUD_API_URL> \\
  --set lnacConnector.lnacHost=<LEGACY_NAC_HOST> \\
  -f deploy/helm/values-onprem-hybrid.yaml`}
            </pre>
          </div>

          <div className="flex justify-between pt-4">
            <button
              onClick={() => setStep('generate-code')}
              className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>
            <button
              onClick={() => setStep('verify')}
              className="flex items-center gap-2 px-6 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors"
            >
              Verify Connection <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Verify */}
      {step === 'verify' && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-6">
          <h2 className="text-lg font-semibold">Verify Connector</h2>
          <p className="text-sm text-muted-foreground">
            Waiting for the on-prem connector to activate and register...
            This page auto-refreshes every 5 seconds.
          </p>

          {connectorsQuery.isLoading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              Checking connector status...
            </div>
          ) : recentConnector ? (
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl p-6 space-y-4">
              <div className="flex items-center gap-3">
                <div className="bg-green-100 dark:bg-green-900/40 p-3 rounded-full">
                  <Wifi className="h-6 w-6 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-green-700 dark:text-green-300">
                    Connector Active
                  </h3>
                  <p className="text-sm text-green-600 dark:text-green-400">
                    {recentConnector.name} is {recentConnector.status}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Status:</span>{' '}
                  <span className="font-medium capitalize">{recentConnector.status}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Tunnel:</span>{' '}
                  <span className="font-medium capitalize">{recentConnector.tunnel_status}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">NeuraNAC Host:</span>{' '}
                  <span className="font-mono text-xs">{recentConnector.legacy_nac_hostname || '-'}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Last Heartbeat:</span>{' '}
                  <span className="text-xs">
                    {recentConnector.last_heartbeat
                      ? new Date(recentConnector.last_heartbeat).toLocaleString()
                      : 'pending'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6 text-center space-y-3">
              <Loader2 className="h-8 w-8 animate-spin text-amber-500 mx-auto" />
              <p className="text-sm text-amber-700 dark:text-amber-300">
                No connector detected yet. Install the connector with the activation code, then
                wait for it to register.
              </p>
            </div>
          )}

          <div className="flex justify-between pt-4">
            <button
              onClick={() => setStep('install-connector')}
              className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>
            {recentConnector && (
              <a
                href="/sites"
                className="flex items-center gap-2 px-6 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
              >
                <CheckCircle2 className="h-4 w-4" /> Done — Go to Site Management
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

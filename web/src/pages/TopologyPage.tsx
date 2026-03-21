import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import {
  Monitor, Router, Shield, Brain, Database, Server, Radio,
  Activity, ArrowRight, RefreshCw, Link2, ChevronRight,
  AlertTriangle, CheckCircle, XCircle, Layers, GitBranch,
  Workflow, Map
} from 'lucide-react'

type ViewTab = 'physical' | 'logical' | 'dataflow' | 'legacy_nac'

const STATUS_COLORS: Record<string, string> = {
  healthy: 'text-green-400 bg-green-500/20',
  degraded: 'text-yellow-400 bg-yellow-500/20',
  unreachable: 'text-red-400 bg-red-500/20',
  unknown: 'text-gray-400 bg-gray-500/20',
  unavailable: 'text-gray-400 bg-gray-500/20',
  active: 'text-green-400 bg-green-500/20',
  connected: 'text-green-400 bg-green-500/20',
  simulated: 'text-blue-400 bg-blue-500/20',
}

const STATUS_ICONS: Record<string, React.ElementType> = {
  healthy: CheckCircle,
  degraded: AlertTriangle,
  unreachable: XCircle,
  unknown: AlertTriangle,
}

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || STATUS_COLORS.unknown
  const Icon = STATUS_ICONS[status] || STATUS_ICONS.unknown
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      <Icon className="h-3 w-3" />
      {status}
    </span>
  )
}

function SummaryCards({ summary }: { summary: any }) {
  if (!summary) return null
  const cards = [
    { label: 'Services', value: `${summary.services_healthy}/${summary.services_total}`, sub: 'healthy', color: summary.services_healthy === summary.services_total ? 'text-green-400' : 'text-yellow-400' },
    { label: 'Infrastructure', value: `${summary.infra_healthy}/${summary.infra_total}`, sub: 'healthy', color: summary.infra_healthy === summary.infra_total ? 'text-green-400' : 'text-yellow-400' },
    { label: 'Network Devices', value: summary.network_devices, sub: 'NADs registered', color: 'text-blue-400' },
    { label: 'Endpoints', value: summary.endpoints, sub: 'profiled', color: 'text-purple-400' },
    { label: 'Active Sessions', value: summary.active_sessions, sub: `of ${summary.total_sessions} total`, color: 'text-green-400' },
    { label: 'Legacy Connections', value: summary.legacy_nac_connections, sub: 'configured', color: 'text-cyan-400' },
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
      {cards.map((c) => (
        <div key={c.label} className="rounded-lg border border-border bg-card p-3">
          <p className="text-xs text-muted-foreground">{c.label}</p>
          <p className={`text-2xl font-bold ${c.color}`}>{c.value}</p>
          <p className="text-xs text-muted-foreground">{c.sub}</p>
        </div>
      ))}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   PHYSICAL TOPOLOGY VIEW
   ═══════════════════════════════════════════════════════════════════════════ */

function PhysicalView({ data }: { data: any }) {
  const layers = data?.layers
  if (!layers) return <p className="text-muted-foreground">No topology data</p>

  const layerConfigs = [
    { name: 'Endpoints', icon: Monitor, color: 'border-purple-500/40 bg-purple-500/5', count: data.endpoints_total },
    { name: 'Network Access Devices', icon: Router, color: 'border-blue-500/40 bg-blue-500/5', items: data.network_devices?.items },
    { name: 'NeuraNAC Application Services', icon: Shield, color: 'border-green-500/40 bg-green-500/5', items: data.services },
    { name: 'Infrastructure', icon: Database, color: 'border-orange-500/40 bg-orange-500/5', items: data.infrastructure },
  ]

  return (
    <div className="space-y-4">
      {layerConfigs.map((layer, idx) => {
        const Icon = layer.icon
        return (
          <div key={layer.name}>
            <div className={`rounded-lg border ${layer.color} p-4`}>
              <div className="flex items-center gap-2 mb-3">
                <Icon className="h-5 w-5 text-muted-foreground" />
                <h3 className="font-semibold text-sm">{layer.name}</h3>
                {layer.count !== undefined && (
                  <span className="ml-auto text-xs text-muted-foreground">{layer.count} total</span>
                )}
                {layer.items && (
                  <span className="ml-auto text-xs text-muted-foreground">{layer.items.length} items</span>
                )}
              </div>

              {/* Endpoint layer — summary only */}
              {idx === 0 && (
                <div className="flex flex-wrap gap-2">
                  <div className="px-3 py-2 rounded bg-purple-500/10 border border-purple-500/20 text-sm">
                    <Monitor className="h-4 w-4 inline mr-1.5 text-purple-400" />
                    {data.endpoints_total} endpoints connected via 802.1X / MAB
                  </div>
                  <div className="px-3 py-2 rounded bg-purple-500/10 border border-purple-500/20 text-sm">
                    <Activity className="h-4 w-4 inline mr-1.5 text-green-400" />
                    {data.sessions?.active || 0} active sessions
                  </div>
                </div>
              )}

              {/* NAD layer */}
              {idx === 1 && layer.items && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {layer.items.map((nad: any) => (
                    <div key={nad.id} className="flex items-center gap-2 px-3 py-2 rounded bg-background border border-border text-sm">
                      <Router className="h-4 w-4 text-blue-400" />
                      <div className="flex-1 min-w-0">
                        <span className="font-mono text-xs">{nad.name}</span>
                        <span className="text-muted-foreground ml-1 text-xs">{nad.ip_address}</span>
                      </div>
                      <StatusBadge status={nad.status || 'active'} />
                    </div>
                  ))}
                </div>
              )}

              {/* Service layers */}
              {idx >= 2 && layer.items && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {layer.items.map((svc: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 px-3 py-2 rounded bg-background border border-border text-sm">
                      <Server className="h-4 w-4 text-muted-foreground" />
                      <div className="flex-1 min-w-0">
                        <span className="font-medium">{svc.name}</span>
                        {svc.port && <span className="text-muted-foreground ml-1 text-xs">:{svc.port}</span>}
                        {svc.latency_ms != null && <span className="text-muted-foreground ml-1 text-xs">({svc.latency_ms}ms)</span>}
                      </div>
                      <StatusBadge status={svc.status} />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Arrow between layers */}
            {idx < layerConfigs.length - 1 && (
              <div className="flex justify-center py-1">
                <div className="flex flex-col items-center text-muted-foreground">
                  <div className="w-px h-3 bg-border" />
                  <ChevronRight className="h-4 w-4 rotate-90" />
                  <div className="w-px h-3 bg-border" />
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   LOGICAL / SERVICE MESH VIEW
   ═══════════════════════════════════════════════════════════════════════════ */

function LogicalView({ data }: { data: any }) {
  const services = data?.services || []
  const infra = data?.infrastructure || []
  const edges = data?.edges || []

  const serviceIcon = (name: string) => {
    if (name.includes('radius')) return Shield
    if (name.includes('policy')) return Shield
    if (name.includes('ai')) return Brain
    if (name.includes('api')) return Server
    if (name.includes('sync')) return RefreshCw
    return Server
  }

  const infraIcon = (type: string) => {
    if (type === 'database') return Database
    if (type === 'cache') return Database
    if (type === 'messaging') return Radio
    return Server
  }

  return (
    <div className="space-y-6">
      {/* Service nodes */}
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Server className="h-4 w-4" /> Application Services
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {/* Web UI (static) */}
          <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Monitor className="h-5 w-5 text-cyan-400" />
              <span className="font-semibold text-sm">Web UI</span>
              <span className="text-xs text-muted-foreground">:3001</span>
              <StatusBadge status="healthy" />
            </div>
            <p className="text-xs text-muted-foreground">React + TypeScript + Vite</p>
          </div>
          {services.map((svc: any) => {
            const Icon = serviceIcon(svc.name)
            return (
              <div key={svc.name} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="h-5 w-5 text-muted-foreground" />
                  <span className="font-semibold text-sm">{svc.name}</span>
                  <StatusBadge status={svc.status} />
                </div>
                <div className="text-xs text-muted-foreground space-y-0.5">
                  {svc.latency_ms != null && <p>Latency: {svc.latency_ms}ms</p>}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Infrastructure nodes */}
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Database className="h-4 w-4" /> Infrastructure
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {infra.map((i: any) => {
            const Icon = infraIcon(i.type)
            return (
              <div key={i.name} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="h-5 w-5 text-muted-foreground" />
                  <span className="font-semibold text-sm">{i.name}</span>
                  <span className="text-xs text-muted-foreground">:{i.port}</span>
                  <StatusBadge status={i.status} />
                </div>
                <p className="text-xs text-muted-foreground capitalize">{i.type}</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* Connections table */}
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <GitBranch className="h-4 w-4" /> Connections ({edges.length})
        </h3>
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-card">
                <th className="text-left px-3 py-2 font-medium">From</th>
                <th className="text-left px-3 py-2 font-medium"></th>
                <th className="text-left px-3 py-2 font-medium">To</th>
                <th className="text-left px-3 py-2 font-medium">Protocol</th>
                <th className="text-left px-3 py-2 font-medium">Label</th>
              </tr>
            </thead>
            <tbody>
              {edges.map((e: any, i: number) => (
                <tr key={i} className="border-b border-border/50 hover:bg-accent/30">
                  <td className="px-3 py-1.5 font-mono text-xs">{e.from}</td>
                  <td className="px-1 py-1.5"><ArrowRight className="h-3 w-3 text-muted-foreground" /></td>
                  <td className="px-3 py-1.5 font-mono text-xs">{e.to}</td>
                  <td className="px-3 py-1.5 text-muted-foreground text-xs">{e.protocol}</td>
                  <td className="px-3 py-1.5 text-xs">{e.label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   DATA FLOW VIEW — RADIUS auth request trace
   ═══════════════════════════════════════════════════════════════════════════ */

function DataFlowView({ data }: { data: any }) {
  const steps = data?.layers?.steps || []

  const stepIcons: Record<string, React.ElementType> = {
    monitor: Monitor, router: Router, shield: Shield, brain: Brain,
    'shield-check': Shield, database: Database, 'alert-triangle': AlertTriangle,
  }

  const stepColors = [
    'border-purple-500/40 bg-purple-500/5',
    'border-blue-500/40 bg-blue-500/5',
    'border-green-500/40 bg-green-500/5',
    'border-yellow-500/40 bg-yellow-500/5',
    'border-cyan-500/40 bg-cyan-500/5',
    'border-green-500/40 bg-green-500/5',
    'border-blue-500/40 bg-blue-500/5',
    'border-orange-500/40 bg-orange-500/5',
    'border-red-500/40 bg-red-500/5',
  ]

  return (
    <div className="space-y-1">
      <p className="text-sm text-muted-foreground mb-4">
        End-to-end trace of a RADIUS authentication request through the NeuraNAC platform.
      </p>
      {steps.map((step: any, idx: number) => {
        const Icon = stepIcons[step.icon] || Server
        const color = stepColors[idx % stepColors.length]
        return (
          <div key={step.step}>
            <div className={`rounded-lg border ${color} p-4 ${step.conditional ? 'border-dashed opacity-80' : ''}`}>
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center text-sm font-bold">
                  {step.step}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <span className="font-semibold text-sm">{step.component}</span>
                    {step.conditional && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">Conditional</span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{step.action}</p>
                  <span className="text-xs font-mono text-muted-foreground">{step.protocol}</span>
                </div>
              </div>
            </div>
            {idx < steps.length - 1 && (
              <div className="flex justify-center py-0.5">
                <div className="w-px h-4 bg-border" />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   NeuraNAC INTEGRATION VIEW
   ═══════════════════════════════════════════════════════════════════════════ */

function NeuraNACView({ data }: { data: any }) {
  const legacyConns = data?.legacy_nac_connections || []
  const integrationPoints = data?.layers?.integration_points || []

  return (
    <div className="space-y-6">
      {/* Legacy Connections */}
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Link2 className="h-4 w-4" /> Legacy Connections ({legacyConns.length})
        </h3>
        {legacyConns.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-muted-foreground text-sm">
            No legacy connections configured. Go to <span className="font-mono">/legacy-nac</span> to create one.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {legacyConns.map((c: any) => (
              <div key={c.id} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Link2 className="h-5 w-5 text-cyan-400" />
                  <span className="font-semibold">{c.name}</span>
                  <StatusBadge status={c.status || 'unknown'} />
                </div>
                <div className="text-xs text-muted-foreground space-y-1">
                  <p>Host: <span className="font-mono">{c.hostname}:{c.port}</span></p>
                  {c.legacy_nac_version && <p>Version: NeuraNAC {c.legacy_nac_version}</p>}
                  <p>Mode: <span className="capitalize">{c.deployment_mode}</span></p>
                  {c.event_stream_status && <p>Event Stream: <span className="capitalize">{c.event_stream_status}</span></p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Integration topology diagram */}
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Workflow className="h-4 w-4" /> Integration Points
        </h3>
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-card">
                <th className="text-left px-3 py-2 font-medium">Integration</th>
                <th className="text-left px-3 py-2 font-medium">Direction</th>
                <th className="text-left px-3 py-2 font-medium">Protocol</th>
                <th className="text-left px-3 py-2 font-medium">Entities</th>
              </tr>
            </thead>
            <tbody>
              {integrationPoints.map((ip: any, i: number) => (
                <tr key={i} className="border-b border-border/50 hover:bg-accent/30">
                  <td className="px-3 py-2 font-medium">{ip.name}</td>
                  <td className="px-3 py-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      ip.direction === 'NeuraNAC → NeuraNAC' ? 'bg-blue-500/20 text-blue-400' :
                      ip.direction === 'NeuraNAC → NeuraNAC' ? 'bg-green-500/20 text-green-400' :
                      'bg-purple-500/20 text-purple-400'
                    }`}>{ip.direction}</span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{ip.protocol}</td>
                  <td className="px-3 py-2 text-xs">{ip.entities?.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Visual flow */}
      <div>
        <h3 className="text-sm font-semibold mb-3">NeuraNAC ↔ NeuraNAC Data Flow</h3>
        <div className="flex items-center justify-center gap-4 p-6 rounded-lg border border-border bg-card">
          <div className="text-center p-4 rounded-lg border border-cyan-500/30 bg-cyan-500/5 min-w-[140px]">
            <Link2 className="h-8 w-8 text-cyan-400 mx-auto mb-2" />
            <p className="font-semibold text-sm">Legacy NAC</p>
            <p className="text-xs text-muted-foreground">ERS + Event Stream</p>
          </div>

          <div className="flex flex-col items-center gap-1 text-muted-foreground">
            <div className="flex items-center gap-1">
              <span className="text-xs">ERS API</span>
              <ArrowRight className="h-4 w-4" />
            </div>
            <div className="flex items-center gap-1">
              <ArrowRight className="h-4 w-4 rotate-180" />
              <span className="text-xs">Bidir Sync</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-xs">Event Stream</span>
              <ArrowRight className="h-4 w-4" />
            </div>
          </div>

          <div className="text-center p-4 rounded-lg border border-green-500/30 bg-green-500/5 min-w-[140px]">
            <Shield className="h-8 w-8 text-green-400 mx-auto mb-2" />
            <p className="font-semibold text-sm">NeuraNAC Platform</p>
            <p className="text-xs text-muted-foreground">API GW + RADIUS</p>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN TOPOLOGY PAGE
   ═══════════════════════════════════════════════════════════════════════════ */

const TABS: { id: ViewTab; label: string; icon: React.ElementType; desc: string }[] = [
  { id: 'physical', label: 'Physical', icon: Layers, desc: 'Endpoints → NADs → Services → Infra' },
  { id: 'logical', label: 'Service Mesh', icon: GitBranch, desc: 'Internal component connections' },
  { id: 'dataflow', label: 'Data Flow', icon: Workflow, desc: 'RADIUS auth request trace' },
  { id: 'legacy_nac', label: 'Legacy Integration', icon: Link2, desc: 'NeuraNAC ↔ NeuraNAC topology' },
]

export default function TopologyPage() {
  const [activeTab, setActiveTab] = useState<ViewTab>('physical')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['topology', activeTab],
    queryFn: () => api.get(`/topology/?view=${activeTab}`).then((r) => r.data),
    refetchInterval: 15000,
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Map className="h-6 w-6" /> Network Topology
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            End-to-end environment visualization with layered component views
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent text-accent-foreground text-sm hover:bg-accent/80"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Summary cards */}
      <SummaryCards summary={data?.summary} />

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-border">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const active = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm border-b-2 transition-colors ${
                active
                  ? 'border-primary text-primary font-medium'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Loading state */}
      {isLoading && !data && (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <RefreshCw className="h-6 w-6 animate-spin mr-2" />
          Loading topology data...
        </div>
      )}

      {/* Tab content */}
      {data && (
        <>
          {activeTab === 'physical' && <PhysicalView data={data} />}
          {activeTab === 'logical' && <LogicalView data={data} />}
          {activeTab === 'dataflow' && <DataFlowView data={data} />}
          {activeTab === 'legacy_nac' && <NeuraNACView data={data} />}
        </>
      )}
    </div>
  )
}

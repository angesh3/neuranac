import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { useSiteStore } from '@/lib/site-store'
import { Link } from 'react-router-dom'
import {
  Globe, Server, Wifi, Activity, RefreshCw,
  Layers, ArrowLeftRight, Database, Shield
} from 'lucide-react'

interface Site {
  id: string
  name: string
  site_type: string
  deployment_mode: string
  api_url: string | null
  status: string
  last_heartbeat: string | null
  is_self: boolean
}

interface Connector {
  id: string
  name: string
  site_name: string
  site_type: string
  status: string
  legacy_nac_hostname: string
  tunnel_status: string
  tunnel_latency_ms: number | null
  events_relayed: number
  errors_count: number
  last_heartbeat: string | null
}

interface NodeInfo {
  id: string
  node_name: string
  role: string
  site_name: string
  site_type: string
  service_type: string | null
  status: string
  active_sessions: number
  cpu_pct: number
  mem_pct: number
  last_heartbeat: string | null
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    healthy: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    connected: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    open: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    degraded: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
    reconnecting: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
    draining: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
    registering: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    disconnected: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    closed: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    inactive: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    unreachable: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[status] || colors.inactive}`}>
      {status}
    </span>
  )
}

export default function SiteManagementPage() {
  const config = useSiteStore((s) => s.config)

  const sitesQuery = useQuery({
    queryKey: ['sites'],
    queryFn: () => api.get('/sites').then((r) => r.data),
    refetchInterval: 15000,
  })

  const connectorsQuery = useQuery({
    queryKey: ['connectors'],
    queryFn: () => api.get('/connectors').then((r) => r.data),
    refetchInterval: 15000,
    enabled: config?.legacyNacEnabled === true,
  })

  const nodesQuery = useQuery({
    queryKey: ['nodes'],
    queryFn: () => api.get('/nodes').then((r) => r.data),
    refetchInterval: 15000,
  })

  const peerQuery = useQuery({
    queryKey: ['peer-status'],
    queryFn: () => api.get('/sites/peer/status').then((r) => r.data),
    refetchInterval: 30000,
  })

  const sites: Site[] = sitesQuery.data?.items || []
  const connectors: Connector[] = connectorsQuery.data?.items || []
  const nodes: NodeInfo[] = nodesQuery.data?.items || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Layers className="h-6 w-6 text-primary" />
            Site Management
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {config?.deploymentMode === 'hybrid' && config?.legacyNacEnabled
              ? 'Scenario 1: Hybrid + NeuraNAC'
              : config?.deploymentMode === 'standalone' && config?.siteType === 'cloud'
              ? 'Scenario 2: Cloud Standalone'
              : config?.deploymentMode === 'standalone' && config?.siteType === 'onprem'
              ? 'Scenario 3: On-Prem Standalone'
              : config?.deploymentMode === 'hybrid' && !config?.legacyNacEnabled
              ? 'Scenario 4: Hybrid (No NeuraNAC)'
              : 'Manage deployment sites, bridge connectors, and node registry'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/sites/onprem-setup"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors"
          >
            <Shield className="h-4 w-4" /> Add On-Prem Connector
          </Link>
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${
            config?.deploymentMode === 'hybrid'
              ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
              : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
          }`}>
            {config?.deploymentMode || 'standalone'}
          </span>
          {config?.legacyNacEnabled && (
            <span className="text-xs px-2 py-1 rounded-full font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300">
              NeuraNAC Enabled
            </span>
          )}
        </div>
      </div>

      {/* Deployment Config Card */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-1">
            <Database className="h-4 w-4" /> Deployment Mode
          </div>
          <p className="text-xl font-bold capitalize">{config?.deploymentMode || 'standalone'}</p>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-1">
            <Server className="h-4 w-4" /> Site Type
          </div>
          <p className="text-xl font-bold capitalize">{config?.siteType || 'onprem'}</p>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-1">
            <ArrowLeftRight className="h-4 w-4" /> Peer Status
          </div>
          <p className="text-xl font-bold capitalize">{peerQuery.data?.peer_status || 'no_peer'}</p>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-1">
            <Activity className="h-4 w-4" /> Total Nodes
          </div>
          <p className="text-xl font-bold">{nodes.length}</p>
        </div>
      </div>

      {/* Sites Table */}
      <div className="bg-card border border-border rounded-lg">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Globe className="h-5 w-5" /> Sites ({sites.length})
          </h2>
          <button
            onClick={() => sitesQuery.refetch()}
            className="text-muted-foreground hover:text-foreground"
          >
            <RefreshCw className={`h-4 w-4 ${sitesQuery.isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Type</th>
                <th className="text-left p-3">Mode</th>
                <th className="text-left p-3">API URL</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Last Heartbeat</th>
                <th className="text-left p-3">Self</th>
              </tr>
            </thead>
            <tbody>
              {sites.map((site) => (
                <tr key={site.id} className="border-b border-border/50 hover:bg-accent/50">
                  <td className="p-3 font-medium">{site.name}</td>
                  <td className="p-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      site.site_type === 'onprem'
                        ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                        : 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
                    }`}>{site.site_type}</span>
                  </td>
                  <td className="p-3 capitalize">{site.deployment_mode}</td>
                  <td className="p-3 text-muted-foreground text-xs font-mono">{site.api_url || '-'}</td>
                  <td className="p-3"><StatusBadge status={site.status} /></td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {site.last_heartbeat ? new Date(site.last_heartbeat).toLocaleString() : '-'}
                  </td>
                  <td className="p-3">
                    {site.is_self && <span className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded-full">self</span>}
                  </td>
                </tr>
              ))}
              {sites.length === 0 && (
                <tr><td colSpan={7} className="p-6 text-center text-muted-foreground">No sites registered</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Connectors Table (only if NeuraNAC enabled) */}
      {config?.legacyNacEnabled && (
        <div className="bg-card border border-border rounded-lg">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Wifi className="h-5 w-5" /> Bridge Connectors ({connectors.length})
            </h2>
            <button
              onClick={() => connectorsQuery.refetch()}
              className="text-muted-foreground hover:text-foreground"
            >
              <RefreshCw className={`h-4 w-4 ${connectorsQuery.isFetching ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="text-left p-3">Name</th>
                  <th className="text-left p-3">Site</th>
                  <th className="text-left p-3">NeuraNAC Host</th>
                  <th className="text-left p-3">Status</th>
                  <th className="text-left p-3">Tunnel</th>
                  <th className="text-left p-3">Latency</th>
                  <th className="text-left p-3">Events</th>
                  <th className="text-left p-3">Errors</th>
                </tr>
              </thead>
              <tbody>
                {connectors.map((c) => (
                  <tr key={c.id} className="border-b border-border/50 hover:bg-accent/50">
                    <td className="p-3 font-medium">{c.name}</td>
                    <td className="p-3">{c.site_name} ({c.site_type})</td>
                    <td className="p-3 font-mono text-xs">{c.legacy_nac_hostname}</td>
                    <td className="p-3"><StatusBadge status={c.status} /></td>
                    <td className="p-3"><StatusBadge status={c.tunnel_status} /></td>
                    <td className="p-3">{c.tunnel_latency_ms != null ? `${c.tunnel_latency_ms}ms` : '-'}</td>
                    <td className="p-3">{c.events_relayed.toLocaleString()}</td>
                    <td className="p-3">{c.errors_count > 0 ? <span className="text-red-500">{c.errors_count}</span> : '0'}</td>
                  </tr>
                ))}
                {connectors.length === 0 && (
                  <tr><td colSpan={8} className="p-6 text-center text-muted-foreground">No connectors registered</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Node Registry Table */}
      <div className="bg-card border border-border rounded-lg">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Server className="h-5 w-5" /> Node Registry ({nodes.length})
          </h2>
          <button
            onClick={() => nodesQuery.refetch()}
            className="text-muted-foreground hover:text-foreground"
          >
            <RefreshCw className={`h-4 w-4 ${nodesQuery.isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="text-left p-3">Node</th>
                <th className="text-left p-3">Role</th>
                <th className="text-left p-3">Site</th>
                <th className="text-left p-3">Service</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Sessions</th>
                <th className="text-left p-3">CPU</th>
                <th className="text-left p-3">Memory</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((n) => (
                <tr key={n.id} className="border-b border-border/50 hover:bg-accent/50">
                  <td className="p-3 font-medium">{n.node_name}</td>
                  <td className="p-3 capitalize">{n.role}</td>
                  <td className="p-3">{n.site_name || '-'} {n.site_type ? `(${n.site_type})` : ''}</td>
                  <td className="p-3">{n.service_type || '-'}</td>
                  <td className="p-3"><StatusBadge status={n.status} /></td>
                  <td className="p-3">{n.active_sessions}</td>
                  <td className="p-3">{n.cpu_pct != null ? `${n.cpu_pct.toFixed(1)}%` : '-'}</td>
                  <td className="p-3">{n.mem_pct != null ? `${n.mem_pct.toFixed(1)}%` : '-'}</td>
                </tr>
              ))}
              {nodes.length === 0 && (
                <tr><td colSpan={8} className="p-6 text-center text-muted-foreground">No nodes in registry</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

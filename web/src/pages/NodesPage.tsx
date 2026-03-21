import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function NodesPage() {
  const { data } = useQuery({ queryKey: ['nodes'], queryFn: () => api.get('/nodes/status').then(r => r.data) })

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Twin-Node Cluster</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {['primary', 'secondary'].map(role => {
          const node = data?.nodes?.find((n: any) => n.role === role)
          return (
            <div key={role} className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold capitalize">{role} Node</h2>
                <span className={`px-2 py-0.5 text-xs rounded ${node?.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{node?.status || 'unknown'}</span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Node ID</span><span className="font-mono text-xs">{node?.node_id || '-'}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Hostname</span><span>{node?.hostname || '-'}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">IP Address</span><span className="font-mono">{node?.ip_address || '-'}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Last Heartbeat</span><span>{node?.last_heartbeat || '-'}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Services</span><span>{node?.services_count ?? '-'}</span></div>
              </div>
            </div>
          )
        })}
      </div>

      <h2 className="text-lg font-semibold mb-3">Sync Status</h2>
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div><p className="text-muted-foreground">Sync Lag</p><p className="text-lg font-bold">{data?.sync_lag_ms ?? '-'} ms</p></div>
          <div><p className="text-muted-foreground">Last Sync</p><p className="text-lg font-bold">{data?.last_sync || '-'}</p></div>
          <div><p className="text-muted-foreground">Changes Pending</p><p className="text-lg font-bold">{data?.pending_changes ?? 0}</p></div>
          <div><p className="text-muted-foreground">Replication Mode</p><p className="text-lg font-bold">{data?.replication_mode || 'active-standby'}</p></div>
        </div>
      </div>
    </div>
  )
}

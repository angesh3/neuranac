import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function AIDataFlowPage() {
  const { data: policies } = useQuery({ queryKey: ['ai-flow-policies'], queryFn: () => api.get('/ai-data-flow/policies').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">AI Data Flow Policies</h1>
        <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">+ New Policy</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Active Policies</p>
          <p className="text-2xl font-bold mt-1">{policies?.items?.filter((p: any) => p.enabled).length ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Blocked Flows (24h)</p>
          <p className="text-2xl font-bold mt-1 text-red-400">{policies?.blocked_count ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Monitored Endpoints</p>
          <p className="text-2xl font-bold mt-1">{policies?.monitored_endpoints ?? 0}</p>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Policy Name</th><th className="p-3">Target Service</th><th className="p-3">Action</th><th className="p-3">DLP Enabled</th><th className="p-3">Status</th>
          </tr></thead>
          <tbody>
            {policies?.items?.length > 0 ? policies.items.map((p: any) => (
              <tr key={p.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                <td className="p-3 font-medium">{p.name}</td>
                <td className="p-3">{p.target_service || 'All'}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${p.action === 'block' ? 'bg-red-500/20 text-red-400' : p.action === 'monitor' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'}`}>{p.action}</span></td>
                <td className="p-3">{p.dlp_enabled ? <span className="text-green-400">Yes</span> : <span className="text-muted-foreground">No</span>}</td>
                <td className="p-3">{p.enabled ? <span className="text-green-400">Active</span> : <span className="text-muted-foreground">Disabled</span>}</td>
              </tr>
            )) : <tr><td colSpan={5} className="p-6 text-center text-muted-foreground">No AI data flow policies configured.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

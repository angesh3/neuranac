import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function AIAgentsPage() {
  const { data } = useQuery({ queryKey: ['ai-agents'], queryFn: () => api.get('/ai-agents/').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">AI Agent Identities</h1>
        <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">+ Register Agent</button>
      </div>
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Agent Name</th><th className="p-3">Type</th><th className="p-3">Model</th><th className="p-3">Auth</th><th className="p-3">Bandwidth</th><th className="p-3">Status</th><th className="p-3">Created</th>
          </tr></thead>
          <tbody>
            {data?.items?.length > 0 ? data.items.map((a: any) => (
              <tr key={a.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                <td className="p-3 font-medium">{a.agent_name}</td>
                <td className="p-3"><span className="px-2 py-0.5 text-xs rounded bg-blue-500/20 text-blue-400">{a.agent_type}</span></td>
                <td className="p-3">{a.model_type || '-'}</td>
                <td className="p-3">{a.auth_method || '-'}</td>
                <td className="p-3">{a.max_bandwidth_mbps ? `${a.max_bandwidth_mbps} Mbps` : 'Unlimited'}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${a.status === 'active' ? 'bg-green-500/20 text-green-400' : a.status === 'revoked' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{a.status}</span></td>
                <td className="p-3 text-muted-foreground text-xs">{a.created_at}</td>
              </tr>
            )) : <tr><td colSpan={7} className="p-6 text-center text-muted-foreground">No AI agents registered. Register your first AI agent identity.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

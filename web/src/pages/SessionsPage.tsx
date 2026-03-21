import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function SessionsPage() {
  const { data } = useQuery({ queryKey: ['sessions'], queryFn: () => api.get('/sessions/?limit=100').then(r => r.data) })
  const { data: countData } = useQuery({ queryKey: ['sessions-count'], queryFn: () => api.get('/sessions/active/count').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">RADIUS Sessions</h1>
        <div className="flex items-center gap-4">
          <span className="px-3 py-1 bg-green-500/20 text-green-400 rounded text-sm">{countData?.active_sessions ?? 0} active</span>
          <span className="text-sm text-muted-foreground">{data?.total ?? 0} total</span>
        </div>
      </div>
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">MAC</th><th className="p-3">Username</th><th className="p-3">NAS IP</th><th className="p-3">EAP</th><th className="p-3">Result</th><th className="p-3">VLAN</th><th className="p-3">Risk</th><th className="p-3">Active</th><th className="p-3">Started</th>
          </tr></thead>
          <tbody>
            {data?.items?.length > 0 ? data.items.map((s: any) => (
              <tr key={s.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                <td className="p-3 font-mono text-xs">{s.endpoint_mac}</td>
                <td className="p-3">{s.username || '-'}</td>
                <td className="p-3 font-mono text-xs">{s.nas_ip}</td>
                <td className="p-3">{s.eap_type || '-'}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${s.auth_result === 'permit' ? 'bg-green-500/20 text-green-400' : s.auth_result === 'deny' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{s.auth_result}</span></td>
                <td className="p-3">{s.vlan_id || '-'}</td>
                <td className="p-3">{s.risk_score != null ? <span className={`${s.risk_score > 70 ? 'text-red-400' : s.risk_score > 40 ? 'text-yellow-400' : 'text-green-400'}`}>{s.risk_score}</span> : '-'}</td>
                <td className="p-3">{s.is_active ? <span className="w-2 h-2 rounded-full bg-green-400 inline-block"/> : <span className="w-2 h-2 rounded-full bg-gray-500 inline-block"/>}</td>
                <td className="p-3 text-muted-foreground text-xs">{s.started_at}</td>
              </tr>
            )) : <tr><td colSpan={9} className="p-6 text-center text-muted-foreground">No sessions recorded yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

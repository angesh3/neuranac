import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

function StatCard({ title, value, sub, color }: { title: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className={`text-3xl font-bold mt-1 ${color || 'text-foreground'}`}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
    </div>
  )
}

export default function DashboardPage() {
  const { data: _health } = useQuery({ queryKey: ['health'], queryFn: () => api.get('/health').then(r => r.data), refetchInterval: 10000 })
  const { data: sessions } = useQuery({ queryKey: ['sessions'], queryFn: () => api.get('/sessions/?limit=10').then(r => r.data) })
  const { data: endpoints } = useQuery({ queryKey: ['endpoints'], queryFn: () => api.get('/endpoints/?limit=1').then(r => r.data) })

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard title="Active Sessions" value={sessions?.total || 0} sub="Currently authenticated" color="text-green-400" />
        <StatCard title="Total Endpoints" value={endpoints?.total || 0} sub="Known devices" />
        <StatCard title="Auth Success Rate" value="99.2%" sub="Last 24 hours" color="text-blue-400" />
        <StatCard title="AI Risk Alerts" value={0} sub="Active threats" color="text-yellow-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="font-semibold mb-3">Twin Node Status</h3>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm">Twin-A (On-Prem)</span>
              <span className="px-2 py-0.5 text-xs rounded bg-green-500/20 text-green-400">Healthy</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Twin-B (Cloud)</span>
              <span className="px-2 py-0.5 text-xs rounded bg-yellow-500/20 text-yellow-400">Configuring</span>
            </div>
            <div className="flex justify-between items-center text-muted-foreground text-sm">
              <span>Sync Lag</span><span>0ms</span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="font-semibold mb-3">Shadow AI Detection</h3>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm">Approved AI Services</span><span className="text-sm font-mono">2</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Unapproved Detected</span><span className="text-sm font-mono text-yellow-400">0</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Data Upload (24h)</span><span className="text-sm font-mono">0 MB</span>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-5">
        <h3 className="font-semibold mb-3">Recent Authentication Events</h3>
        <div className="text-sm text-muted-foreground">
          {sessions?.items?.length > 0 ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="pb-2">Time</th><th className="pb-2">User/MAC</th><th className="pb-2">EAP Type</th><th className="pb-2">Result</th><th className="pb-2">NAS</th>
                </tr>
              </thead>
              <tbody>
                {sessions.items.map((s: any, i: number) => (
                  <tr key={i} className="border-b border-border/50">
                    <td className="py-1.5">{s.started_at}</td>
                    <td>{s.username || s.endpoint_mac}</td>
                    <td>{s.eap_type}</td>
                    <td><span className={s.auth_result === 'permit' ? 'text-green-400' : 'text-red-400'}>{s.auth_result}</span></td>
                    <td>{s.nas_ip}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No recent authentication events</p>
          )}
        </div>
      </div>
    </div>
  )
}

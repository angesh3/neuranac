import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function PosturePage() {
  const { data: policies } = useQuery({ queryKey: ['posture-policies'], queryFn: () => api.get('/posture/policies').then(r => r.data) })
  const { data: results } = useQuery({ queryKey: ['posture-results'], queryFn: () => api.get('/posture/results?limit=50').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Posture Assessment</h1>
        <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">+ New Policy</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Posture Policies</p>
          <p className="text-2xl font-bold mt-1">{policies?.total ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Compliant Endpoints</p>
          <p className="text-2xl font-bold mt-1 text-green-400">{results?.compliant ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Non-Compliant</p>
          <p className="text-2xl font-bold mt-1 text-red-400">{results?.non_compliant ?? 0}</p>
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-3">Recent Assessments</h2>
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Endpoint</th><th className="p-3">Policy</th><th className="p-3">OS</th><th className="p-3">AV</th><th className="p-3">Firewall</th><th className="p-3">Result</th><th className="p-3">Assessed</th>
          </tr></thead>
          <tbody>
            {results?.items?.length > 0 ? results.items.map((r: any) => (
              <tr key={r.id} className="border-b border-border/50 hover:bg-accent/50">
                <td className="p-3 font-mono text-xs">{r.endpoint_mac}</td>
                <td className="p-3">{r.policy_name || '-'}</td>
                <td className="p-3">{r.os_compliant ? <span className="text-green-400">Pass</span> : <span className="text-red-400">Fail</span>}</td>
                <td className="p-3">{r.av_compliant ? <span className="text-green-400">Pass</span> : <span className="text-red-400">Fail</span>}</td>
                <td className="p-3">{r.fw_compliant ? <span className="text-green-400">Pass</span> : <span className="text-red-400">Fail</span>}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${r.overall_compliant ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>{r.overall_compliant ? 'Compliant' : 'Non-Compliant'}</span></td>
                <td className="p-3 text-muted-foreground text-xs">{r.assessed_at}</td>
              </tr>
            )) : <tr><td colSpan={7} className="p-6 text-center text-muted-foreground">No posture assessments recorded.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

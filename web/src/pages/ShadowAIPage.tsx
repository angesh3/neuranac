import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function ShadowAIPage() {
  const { data: detections } = useQuery({ queryKey: ['shadow-detections'], queryFn: () => api.get('/ai-data-flow/detections').then(r => r.data) })
  const { data: services } = useQuery({ queryKey: ['ai-services'], queryFn: () => api.get('/ai-data-flow/services').then(r => r.data) })

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Shadow AI Detection</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Detections (24h)</p>
          <p className="text-2xl font-bold mt-1">{detections?.total ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Known AI Services</p>
          <p className="text-2xl font-bold mt-1">{services?.total ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Unapproved Services</p>
          <p className="text-2xl font-bold mt-1 text-red-400">{services?.items?.filter((s: any) => !s.is_approved).length ?? 0}</p>
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-3">Recent Detections</h2>
      <div className="rounded-lg border border-border bg-card mb-6">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Endpoint</th><th className="p-3">User</th><th className="p-3">Type</th><th className="p-3">Upload</th><th className="p-3">Download</th><th className="p-3">Action</th><th className="p-3">Detected</th>
          </tr></thead>
          <tbody>
            {detections?.items?.length > 0 ? detections.items.map((d: any, i: number) => (
              <tr key={d.id || i} className="border-b border-border/50 hover:bg-accent/50">
                <td className="p-3 font-mono text-xs">{d.endpoint_mac}</td>
                <td className="p-3">{d.user_id || '-'}</td>
                <td className="p-3"><span className="px-2 py-0.5 text-xs rounded bg-orange-500/20 text-orange-400">{d.detection_type}</span></td>
                <td className="p-3">{d.bytes_uploaded ? `${(d.bytes_uploaded / 1024 / 1024).toFixed(1)} MB` : '-'}</td>
                <td className="p-3">{d.bytes_downloaded ? `${(d.bytes_downloaded / 1024 / 1024).toFixed(1)} MB` : '-'}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${d.action_taken === 'blocked' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{d.action_taken}</span></td>
                <td className="p-3 text-muted-foreground text-xs">{d.detected_at}</td>
              </tr>
            )) : <tr><td colSpan={7} className="p-6 text-center text-muted-foreground">No shadow AI activity detected.</td></tr>}
          </tbody>
        </table>
      </div>

      <h2 className="text-lg font-semibold mb-3">AI Service Registry</h2>
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Service</th><th className="p-3">Category</th><th className="p-3">Risk</th><th className="p-3">Approved</th>
          </tr></thead>
          <tbody>
            {services?.items?.length > 0 ? services.items.map((s: any, i: number) => (
              <tr key={s.id || i} className="border-b border-border/50 hover:bg-accent/50">
                <td className="p-3 font-medium">{s.name}</td>
                <td className="p-3">{s.category}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${s.risk_level === 'high' ? 'bg-red-500/20 text-red-400' : s.risk_level === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'}`}>{s.risk_level}</span></td>
                <td className="p-3">{s.is_approved ? <span className="text-green-400">Yes</span> : <span className="text-red-400">No</span>}</td>
              </tr>
            )) : <tr><td colSpan={4} className="p-6 text-center text-muted-foreground">No AI services in registry.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function SegmentationPage() {
  const { data: sgts } = useQuery({ queryKey: ['sgts'], queryFn: () => api.get('/segmentation/').then(r => r.data) })
  const { data: matrix } = useQuery({ queryKey: ['seg-matrix'], queryFn: () => api.get('/segmentation/matrix').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">TrustSec Segmentation</h1>
        <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">+ New SGT</button>
      </div>

      <h2 className="text-lg font-semibold mb-3">Security Group Tags</h2>
      <div className="rounded-lg border border-border bg-card mb-6">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Name</th><th className="p-3">Value</th><th className="p-3">Description</th><th className="p-3">Assigned</th>
          </tr></thead>
          <tbody>
            {sgts?.items?.length > 0 ? sgts.items.map((s: any) => (
              <tr key={s.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                <td className="p-3 font-medium">{s.name}</td>
                <td className="p-3 font-mono">{s.value}</td>
                <td className="p-3 text-muted-foreground">{s.description || '-'}</td>
                <td className="p-3">{s.assigned_count ?? 0}</td>
              </tr>
            )) : <tr><td colSpan={4} className="p-6 text-center text-muted-foreground">No SGTs configured.</td></tr>}
          </tbody>
        </table>
      </div>

      <h2 className="text-lg font-semibold mb-3">Policy Matrix</h2>
      <div className="rounded-lg border border-border bg-card p-4">
        {matrix?.matrix?.length > 0 ? (
          <div className="overflow-x-auto">
            <p className="text-sm text-muted-foreground mb-2">{matrix.matrix.length} rules defined</p>
            <div className="grid gap-2">
              {matrix.matrix.slice(0, 10).map((rule: any, i: number) => (
                <div key={i} className="flex items-center gap-3 text-sm p-2 rounded bg-accent/30">
                  <span className="font-mono px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded">{rule.src_sgt}</span>
                  <span className="text-muted-foreground">→</span>
                  <span className="font-mono px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded">{rule.dst_sgt}</span>
                  <span className={`ml-auto px-2 py-0.5 text-xs rounded ${rule.action === 'permit' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>{rule.action}</span>
                </div>
              ))}
            </div>
          </div>
        ) : <p className="text-muted-foreground text-center">No segmentation matrix rules configured.</p>}
      </div>
    </div>
  )
}

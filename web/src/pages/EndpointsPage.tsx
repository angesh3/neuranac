import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function EndpointsPage() {
  const { data } = useQuery({ queryKey: ['endpoints'], queryFn: () => api.get('/endpoints/?limit=100').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Endpoints</h1>
        <span className="text-sm text-muted-foreground">{data?.total ?? 0} total</span>
      </div>
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">MAC</th><th className="p-3">Hostname</th><th className="p-3">Type</th><th className="p-3">Vendor</th><th className="p-3">OS</th><th className="p-3">Status</th><th className="p-3">Last Seen</th>
          </tr></thead>
          <tbody>
            {data?.items?.length > 0 ? data.items.map((ep: any) => (
              <tr key={ep.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                <td className="p-3 font-mono text-xs">{ep.mac_address}</td>
                <td className="p-3">{ep.hostname || '-'}</td>
                <td className="p-3">{ep.device_type || '-'}</td>
                <td className="p-3">{ep.vendor || '-'}</td>
                <td className="p-3">{ep.os || '-'}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${ep.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>{ep.status}</span></td>
                <td className="p-3 text-muted-foreground text-xs">{ep.last_seen}</td>
              </tr>
            )) : <tr><td colSpan={7} className="p-6 text-center text-muted-foreground">No endpoints discovered yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

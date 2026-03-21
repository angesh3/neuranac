import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function NetworkDevicesPage() {
  const { data } = useQuery({ queryKey: ['network-devices'], queryFn: () => api.get('/network-devices/').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Network Access Devices</h1>
        <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">+ Add Device</button>
      </div>
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Name</th><th className="p-3">IP Address</th><th className="p-3">Vendor</th><th className="p-3">Model</th><th className="p-3">RadSec</th><th className="p-3">Status</th><th className="p-3">Last Seen</th>
          </tr></thead>
          <tbody>
            {data?.items?.length > 0 ? data.items.map((d: any) => (
              <tr key={d.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                <td className="p-3 font-medium">{d.name}</td>
                <td className="p-3 font-mono text-xs">{d.ip_address}</td>
                <td className="p-3">{d.vendor || '-'}</td>
                <td className="p-3">{d.model || '-'}</td>
                <td className="p-3">{d.radsec_enabled ? <span className="text-green-400">Yes</span> : <span className="text-muted-foreground">No</span>}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${d.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{d.status}</span></td>
                <td className="p-3 text-muted-foreground text-xs">{d.last_seen || 'Never'}</td>
              </tr>
            )) : <tr><td colSpan={7} className="p-6 text-center text-muted-foreground">No network devices configured. Add your first switch, AP, or WLC.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

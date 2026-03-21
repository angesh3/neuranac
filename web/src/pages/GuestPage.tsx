import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function GuestPage() {
  const { data: portals } = useQuery({ queryKey: ['guest-portals'], queryFn: () => api.get('/guest/portals').then(r => r.data) })
  const { data: accounts } = useQuery({ queryKey: ['guest-accounts'], queryFn: () => api.get('/guest/accounts').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Guest Access</h1>
        <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">+ Create Guest Account</button>
      </div>

      <h2 className="text-lg font-semibold mb-3">Guest Portals</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {portals?.items?.length > 0 ? portals.items.map((p: any) => (
          <div key={p.id} className="rounded-lg border border-border bg-card p-4 hover:bg-accent/50 cursor-pointer">
            <h3 className="font-medium">{p.name}</h3>
            <p className="text-xs text-muted-foreground mt-1">{p.portal_type}</p>
            <div className="flex items-center justify-between mt-3">
              <span className={`px-2 py-0.5 text-xs rounded ${p.enabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>{p.enabled ? 'Active' : 'Disabled'}</span>
              <span className="text-xs text-muted-foreground">{p.url || 'No URL'}</span>
            </div>
          </div>
        )) : <div className="col-span-3 rounded-lg border border-border bg-card p-6 text-center text-muted-foreground">No guest portals configured.</div>}
      </div>

      <h2 className="text-lg font-semibold mb-3">Guest Accounts</h2>
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Username</th><th className="p-3">Email</th><th className="p-3">Sponsor</th><th className="p-3">Expires</th><th className="p-3">Status</th>
          </tr></thead>
          <tbody>
            {accounts?.items?.length > 0 ? accounts.items.map((a: any) => (
              <tr key={a.id} className="border-b border-border/50 hover:bg-accent/50">
                <td className="p-3 font-medium">{a.username}</td>
                <td className="p-3">{a.email || '-'}</td>
                <td className="p-3">{a.sponsor || '-'}</td>
                <td className="p-3 text-xs">{a.expires_at || 'Never'}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${a.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>{a.status}</span></td>
              </tr>
            )) : <tr><td colSpan={5} className="p-6 text-center text-muted-foreground">No guest accounts.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

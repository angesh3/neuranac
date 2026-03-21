import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function IdentityPage() {
  const { data } = useQuery({ queryKey: ['identity-sources'], queryFn: () => api.get('/identity-sources/').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Identity Sources</h1>
        <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">+ Add Source</button>
      </div>
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Name</th><th className="p-3">Type</th><th className="p-3">Host</th><th className="p-3">Users</th><th className="p-3">Priority</th><th className="p-3">Status</th>
          </tr></thead>
          <tbody>
            {data?.items?.length > 0 ? data.items.map((src: any) => (
              <tr key={src.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                <td className="p-3 font-medium">{src.name}</td>
                <td className="p-3"><span className="px-2 py-0.5 text-xs rounded bg-blue-500/20 text-blue-400">{src.source_type}</span></td>
                <td className="p-3 font-mono text-xs">{src.host || '-'}</td>
                <td className="p-3">{src.user_count ?? '-'}</td>
                <td className="p-3">{src.priority ?? '-'}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${src.status === 'connected' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>{src.status}</span></td>
              </tr>
            )) : <tr><td colSpan={6} className="p-6 text-center text-muted-foreground">No identity sources configured. Add Active Directory, LDAP, or SAML.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

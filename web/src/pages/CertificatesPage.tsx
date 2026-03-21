import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function CertificatesPage() {
  const { data } = useQuery({ queryKey: ['certificates'], queryFn: () => api.get('/certificates/').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Certificate Management</h1>
        <div className="flex gap-2">
          <button className="px-4 py-2 bg-accent text-accent-foreground rounded-md text-sm">Generate CSR</button>
          <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">Import Certificate</button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">System Certificates</p>
          <p className="text-2xl font-bold mt-1">{data?.items?.filter((c: any) => c.cert_type === 'system').length ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Trusted CAs</p>
          <p className="text-2xl font-bold mt-1">{data?.items?.filter((c: any) => c.cert_type === 'ca').length ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Expiring Soon</p>
          <p className="text-2xl font-bold mt-1 text-yellow-400">{data?.expiring_soon ?? 0}</p>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Subject</th><th className="p-3">Type</th><th className="p-3">Issuer</th><th className="p-3">Expires</th><th className="p-3">Status</th>
          </tr></thead>
          <tbody>
            {data?.items?.length > 0 ? data.items.map((c: any) => (
              <tr key={c.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                <td className="p-3 font-medium">{c.subject_cn}</td>
                <td className="p-3"><span className="px-2 py-0.5 text-xs rounded bg-blue-500/20 text-blue-400">{c.cert_type}</span></td>
                <td className="p-3 text-muted-foreground">{c.issuer_cn || 'Self-signed'}</td>
                <td className="p-3 text-xs">{c.expires_at}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${c.status === 'valid' ? 'bg-green-500/20 text-green-400' : c.status === 'expiring' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'}`}>{c.status}</span></td>
              </tr>
            )) : <tr><td colSpan={5} className="p-6 text-center text-muted-foreground">No certificates installed.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

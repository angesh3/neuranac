import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function AuditPage() {
  const { data } = useQuery({ queryKey: ['audit-logs'], queryFn: () => api.get('/audit/?limit=100').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Audit Logs</h1>
        <button className="px-4 py-2 bg-accent text-accent-foreground rounded-md text-sm hover:bg-accent/90">Export CSV</button>
      </div>
      <div className="rounded-lg border border-border bg-card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="p-3">Timestamp</th><th className="p-3">User</th><th className="p-3">Action</th><th className="p-3">Resource</th><th className="p-3">Result</th><th className="p-3">IP</th>
          </tr></thead>
          <tbody>
            {data?.items?.length > 0 ? data.items.map((log: any) => (
              <tr key={log.id} className="border-b border-border/50 hover:bg-accent/50">
                <td className="p-3 text-muted-foreground text-xs font-mono">{log.timestamp}</td>
                <td className="p-3">{log.username || log.user_id || '-'}</td>
                <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${log.action === 'DELETE' ? 'bg-red-500/20 text-red-400' : log.action === 'CREATE' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'}`}>{log.action}</span></td>
                <td className="p-3 font-mono text-xs">{log.resource_type}/{log.resource_id}</td>
                <td className="p-3"><span className={`${log.success ? 'text-green-400' : 'text-red-400'}`}>{log.success ? 'OK' : 'FAIL'}</span></td>
                <td className="p-3 font-mono text-xs">{log.source_ip || '-'}</td>
              </tr>
            )) : <tr><td colSpan={6} className="p-6 text-center text-muted-foreground">No audit log entries.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

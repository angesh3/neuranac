import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

export default function LicensesPage() {
  const { data: license, isLoading } = useQuery({
    queryKey: ['licenses'],
    queryFn: () => api.get('/api/v1/licenses').then(r => r.data),
  })

  const { data: usage } = useQuery({
    queryKey: ['licenses', 'usage'],
    queryFn: () => api.get('/api/v1/licenses/usage').then(r => r.data),
  })

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Licenses</h1>
        <p className="text-sm text-gray-500 mt-1">Manage your NeuraNAC license and feature entitlements</p>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-12">Loading license information...</div>
      ) : (
        <>
          {/* License Info Card */}
          <div className="bg-white rounded-lg border p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">License Details</h2>
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                license?.status === 'active' ? 'bg-green-100 text-green-800' :
                license?.status === 'trial' ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              }`}>
                {license?.status || 'Unknown'}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-6">
              <div>
                <p className="text-sm text-gray-500">License Tier</p>
                <p className="font-semibold mt-1">{license?.tier || 'Trial'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">License Key</p>
                <p className="font-mono text-sm mt-1">{license?.key ? `${license.key.slice(0, 8)}...` : 'Not set'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Expires</p>
                <p className="font-semibold mt-1">{license?.expires_at ? new Date(license.expires_at).toLocaleDateString() : 'N/A'}</p>
              </div>
            </div>
          </div>

          {/* Usage */}
          <div className="bg-white rounded-lg border p-6">
            <h2 className="text-lg font-semibold mb-4">Usage</h2>
            <div className="space-y-4">
              {[
                { label: 'Endpoints', used: usage?.endpoints || 0, limit: usage?.endpoint_limit || 1000 },
                { label: 'Network Devices', used: usage?.devices || 0, limit: usage?.device_limit || 100 },
                { label: 'Concurrent Sessions', used: usage?.sessions || 0, limit: usage?.session_limit || 5000 },
                { label: 'AI Queries/day', used: usage?.ai_queries || 0, limit: usage?.ai_query_limit || 1000 },
              ].map(u => (
                <div key={u.label}>
                  <div className="flex justify-between text-sm mb-1">
                    <span>{u.label}</span>
                    <span className="text-gray-500">{u.used.toLocaleString()} / {u.limit.toLocaleString()}</span>
                  </div>
                  <div className="w-full h-2 bg-gray-200 rounded-full">
                    <div
                      className={`h-2 rounded-full ${u.used / u.limit > 0.9 ? 'bg-red-500' : u.used / u.limit > 0.7 ? 'bg-yellow-500' : 'bg-green-500'}`}
                      style={{ width: `${Math.min(100, (u.used / u.limit) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Features */}
          <div className="bg-white rounded-lg border p-6">
            <h2 className="text-lg font-semibold mb-4">Feature Entitlements</h2>
            <div className="grid grid-cols-2 gap-3">
              {(license?.features || [
                { name: 'RADIUS/TACACS+', enabled: true },
                { name: 'Legacy Integration', enabled: true },
                { name: 'AI Profiling', enabled: true },
                { name: 'AI Chat Mode', enabled: true },
                { name: 'Event Stream', enabled: license?.tier !== 'trial' },
                { name: 'Multi-site Sync', enabled: license?.tier === 'enterprise' },
                { name: 'SIEM Integration', enabled: license?.tier !== 'trial' },
                { name: 'Custom Playbooks', enabled: license?.tier === 'enterprise' },
              ]).map((f: any) => (
                <div key={f.name} className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                  <span className={`w-2 h-2 rounded-full ${f.enabled ? 'bg-green-500' : 'bg-gray-300'}`} />
                  <span className={`text-sm ${f.enabled ? '' : 'text-gray-400'}`}>{f.name}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

export default function SIEMPage() {
  const [showAddForm, setShowAddForm] = useState(false)

  const { data: destinations, isLoading, refetch } = useQuery({
    queryKey: ['siem', 'destinations'],
    queryFn: () => api.get('/api/v1/siem/destinations').then(r => r.data),
  })

  const { data: stats } = useQuery({
    queryKey: ['siem', 'stats'],
    queryFn: () => api.get('/api/v1/siem/stats').then(r => r.data),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/siem/destinations/${id}`),
    onSuccess: () => refetch(),
  })

  const testMut = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/siem/destinations/${id}/test`),
  })

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">SIEM & SOAR Integration</h1>
          <p className="text-sm text-gray-500 mt-1">Forward security events to external SIEM/SOAR platforms</p>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700"
        >
          Add Destination
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Forwarded', value: stats?.total_forwarded || 0 },
          { label: 'Last 24h', value: stats?.last_24h || 0 },
          { label: 'Failed', value: stats?.failed || 0 },
          { label: 'Active Destinations', value: stats?.active_count || 0 },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-lg border p-4">
            <p className="text-sm text-gray-500">{s.label}</p>
            <p className="text-2xl font-bold mt-1">{s.value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      {/* Destinations Table */}
      <div className="bg-white rounded-lg border">
        <div className="p-4 border-b">
          <h2 className="font-semibold">SIEM Destinations</h2>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-gray-400">Loading...</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Type</th>
                <th className="text-left p-3">Endpoint</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Events Sent</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(destinations?.items || []).map((d: any) => (
                <tr key={d.id} className="border-t hover:bg-gray-50">
                  <td className="p-3 font-medium">{d.name}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 bg-gray-100 rounded text-xs">{d.type}</span>
                  </td>
                  <td className="p-3 text-gray-500 font-mono text-xs">{d.endpoint}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${d.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {d.status}
                    </span>
                  </td>
                  <td className="p-3">{d.events_sent?.toLocaleString() || 0}</td>
                  <td className="p-3 text-center space-x-2">
                    <button onClick={() => testMut.mutate(d.id)} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs hover:bg-blue-200">Test</button>
                    <button onClick={() => deleteMut.mutate(d.id)} className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs hover:bg-red-200">Delete</button>
                  </td>
                </tr>
              ))}
              {(!destinations?.items || destinations.items.length === 0) && (
                <tr><td colSpan={6} className="p-8 text-center text-gray-400">No SIEM destinations configured</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

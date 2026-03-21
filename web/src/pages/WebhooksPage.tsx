import { useQuery, useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

export default function WebhooksPage() {
  const { data: webhooks, isLoading, refetch } = useQuery({
    queryKey: ['webhooks'],
    queryFn: () => api.get('/api/v1/webhooks').then(r => r.data),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/webhooks/${id}`),
    onSuccess: () => refetch(),
  })

  const testMut = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/webhooks/${id}/test`),
  })

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Webhooks & Plugins</h1>
          <p className="text-sm text-gray-500 mt-1">Subscribe to system events and deliver them to external endpoints</p>
        </div>
        <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700">
          Create Webhook
        </button>
      </div>

      <div className="bg-white rounded-lg border">
        <div className="p-4 border-b">
          <h2 className="font-semibold">Configured Webhooks</h2>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-gray-400">Loading...</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">URL</th>
                <th className="text-left p-3">Events</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Last Delivery</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(webhooks?.items || []).map((w: any) => (
                <tr key={w.id} className="border-t hover:bg-gray-50">
                  <td className="p-3 font-medium">{w.name}</td>
                  <td className="p-3 text-gray-500 font-mono text-xs max-w-xs truncate">{w.url}</td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-1">
                      {(w.events || []).slice(0, 3).map((e: string) => (
                        <span key={e} className="px-1.5 py-0.5 bg-gray-100 rounded text-xs">{e}</span>
                      ))}
                      {(w.events || []).length > 3 && (
                        <span className="text-xs text-gray-400">+{w.events.length - 3}</span>
                      )}
                    </div>
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${w.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {w.active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="p-3 text-gray-500 text-xs">{w.last_delivery ? new Date(w.last_delivery).toLocaleString() : '—'}</td>
                  <td className="p-3 text-center space-x-2">
                    <button onClick={() => testMut.mutate(w.id)} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs hover:bg-blue-200">Test</button>
                    <button onClick={() => deleteMut.mutate(w.id)} className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs hover:bg-red-200">Delete</button>
                  </td>
                </tr>
              ))}
              {(!webhooks?.items || webhooks.items.length === 0) && (
                <tr><td colSpan={6} className="p-8 text-center text-gray-400">No webhooks configured</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

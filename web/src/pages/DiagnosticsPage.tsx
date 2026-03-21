import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { useState } from 'react'

export default function DiagnosticsPage() {
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: () => api.get('/health/').then(r => r.data) })
  const [testMac, setTestMac] = useState('')

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Diagnostics & Troubleshooting</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-lg font-semibold mb-3">System Health</h2>
          <div className="space-y-2 text-sm">
            {['database', 'redis', 'nats', 'radius', 'policy_engine', 'ai_engine'].map(svc => (
              <div key={svc} className="flex justify-between items-center">
                <span className="capitalize">{svc.replace('_', ' ')}</span>
                <span className={`px-2 py-0.5 text-xs rounded ${health?.[svc] === 'healthy' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>{health?.[svc] || 'unknown'}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-lg font-semibold mb-3">Auth Test</h2>
          <p className="text-sm text-muted-foreground mb-3">Simulate a RADIUS authentication for an endpoint MAC address.</p>
          <div className="flex gap-2">
            <input className="flex-1 px-3 py-2 rounded bg-background border border-border text-sm font-mono" placeholder="AA:BB:CC:DD:EE:FF" value={testMac} onChange={e => setTestMac(e.target.value)} />
            <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">Test</button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-lg font-semibold mb-3">RADIUS Live Log</h2>
          <div className="bg-background rounded p-3 h-48 overflow-auto font-mono text-xs text-muted-foreground">
            <p>Waiting for RADIUS events...</p>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-lg font-semibold mb-3">Quick Actions</h2>
          <div className="space-y-2">
            <button className="w-full text-left px-3 py-2 rounded bg-accent/30 hover:bg-accent/50 text-sm">Flush Redis Cache</button>
            <button className="w-full text-left px-3 py-2 rounded bg-accent/30 hover:bg-accent/50 text-sm">Restart RADIUS Service</button>
            <button className="w-full text-left px-3 py-2 rounded bg-accent/30 hover:bg-accent/50 text-sm">Download Support Bundle</button>
            <button className="w-full text-left px-3 py-2 rounded bg-accent/30 hover:bg-accent/50 text-sm">Run Connectivity Check</button>
          </div>
        </div>
      </div>
    </div>
  )
}

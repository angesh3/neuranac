import { useState } from 'react'

export default function SettingsPage() {
  const [tab, setTab] = useState<'general' | 'radius' | 'certificates' | 'backup'>('general')

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">System Settings</h1>
      <div className="flex gap-2 mb-6">
        {(['general', 'radius', 'certificates', 'backup'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-1.5 rounded text-sm capitalize ${tab === t ? 'bg-primary/10 text-primary' : 'text-muted-foreground'}`}>{t}</button>
        ))}
      </div>

      {tab === 'general' && (
        <div className="rounded-lg border border-border bg-card p-6 space-y-4">
          <div><label className="block text-sm text-muted-foreground mb-1">Hostname</label><input className="w-full px-3 py-2 rounded bg-background border border-border text-sm" defaultValue="neuranac-primary" /></div>
          <div><label className="block text-sm text-muted-foreground mb-1">Domain</label><input className="w-full px-3 py-2 rounded bg-background border border-border text-sm" defaultValue="neuranac.local" /></div>
          <div><label className="block text-sm text-muted-foreground mb-1">Timezone</label><input className="w-full px-3 py-2 rounded bg-background border border-border text-sm" defaultValue="UTC" /></div>
          <div><label className="block text-sm text-muted-foreground mb-1">Session Timeout (min)</label><input type="number" className="w-full px-3 py-2 rounded bg-background border border-border text-sm" defaultValue={30} /></div>
          <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">Save Changes</button>
        </div>
      )}

      {tab === 'radius' && (
        <div className="rounded-lg border border-border bg-card p-6 space-y-4">
          <div><label className="block text-sm text-muted-foreground mb-1">Auth Port</label><input type="number" className="w-full px-3 py-2 rounded bg-background border border-border text-sm" defaultValue={1812} /></div>
          <div><label className="block text-sm text-muted-foreground mb-1">Accounting Port</label><input type="number" className="w-full px-3 py-2 rounded bg-background border border-border text-sm" defaultValue={1813} /></div>
          <div><label className="block text-sm text-muted-foreground mb-1">CoA Port</label><input type="number" className="w-full px-3 py-2 rounded bg-background border border-border text-sm" defaultValue={3799} /></div>
          <div><label className="block text-sm text-muted-foreground mb-1">Max Request Timeout (s)</label><input type="number" className="w-full px-3 py-2 rounded bg-background border border-border text-sm" defaultValue={5} /></div>
          <div className="flex items-center gap-2"><input type="checkbox" defaultChecked /><label className="text-sm">Enable RadSec (RADIUS over TLS)</label></div>
          <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">Save RADIUS Settings</button>
        </div>
      )}

      {tab === 'certificates' && (
        <div className="rounded-lg border border-border bg-card p-6">
          <p className="text-sm text-muted-foreground mb-4">Manage system and RADIUS certificates. Upload CA certs, server certs, and configure EAP-TLS trust stores.</p>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded bg-accent/30"><span className="text-sm">System Certificate</span><span className="text-xs text-muted-foreground">Expires: N/A</span></div>
            <div className="flex items-center justify-between p-3 rounded bg-accent/30"><span className="text-sm">RADIUS Server Certificate</span><span className="text-xs text-muted-foreground">Expires: N/A</span></div>
            <div className="flex items-center justify-between p-3 rounded bg-accent/30"><span className="text-sm">Trusted CA Store</span><span className="text-xs text-muted-foreground">0 CAs</span></div>
          </div>
          <button className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">Upload Certificate</button>
        </div>
      )}

      {tab === 'backup' && (
        <div className="rounded-lg border border-border bg-card p-6">
          <p className="text-sm text-muted-foreground mb-4">Create and restore configuration backups. Scheduled backups can be configured for automatic nightly export.</p>
          <div className="space-y-3">
            <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 mr-2">Create Backup Now</button>
            <button className="px-4 py-2 bg-accent text-accent-foreground rounded-md text-sm hover:bg-accent/90">Restore from Backup</button>
          </div>
          <div className="mt-4 p-3 rounded bg-accent/30 text-sm text-muted-foreground">No backups available.</div>
        </div>
      )}
    </div>
  )
}

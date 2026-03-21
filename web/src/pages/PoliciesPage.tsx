import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { useState } from 'react'

export default function PoliciesPage() {
  const [tab, setTab] = useState<'sets' | 'profiles'>('sets')
  const { data: policySets } = useQuery({ queryKey: ['policy-sets'], queryFn: () => api.get('/policies/').then(r => r.data) })
  const { data: authProfiles } = useQuery({ queryKey: ['auth-profiles'], queryFn: () => api.get('/policies/auth-profiles/').then(r => r.data) })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Access Policies</h1>
        <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">
          + New Policy Set
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        <button onClick={() => setTab('sets')} className={`px-3 py-1.5 rounded text-sm ${tab === 'sets' ? 'bg-primary/10 text-primary' : 'text-muted-foreground'}`}>Policy Sets</button>
        <button onClick={() => setTab('profiles')} className={`px-3 py-1.5 rounded text-sm ${tab === 'profiles' ? 'bg-primary/10 text-primary' : 'text-muted-foreground'}`}>Authorization Profiles</button>
      </div>

      {tab === 'sets' && (
        <div className="rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground">
              <th className="p-3">Name</th><th className="p-3">Priority</th><th className="p-3">Status</th><th className="p-3">Created</th>
            </tr></thead>
            <tbody>
              {policySets?.items?.length > 0 ? policySets.items.map((ps: any) => (
                <tr key={ps.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                  <td className="p-3 font-medium">{ps.name}</td>
                  <td className="p-3">{ps.priority}</td>
                  <td className="p-3"><span className={`px-2 py-0.5 text-xs rounded ${ps.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{ps.status}</span></td>
                  <td className="p-3 text-muted-foreground">{ps.created_at}</td>
                </tr>
              )) : <tr><td colSpan={4} className="p-6 text-center text-muted-foreground">No policy sets configured. Create your first policy set to get started.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'profiles' && (
        <div className="rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground">
              <th className="p-3">Name</th><th className="p-3">VLAN</th><th className="p-3">SGT</th><th className="p-3">CoA Action</th>
            </tr></thead>
            <tbody>
              {authProfiles?.items?.length > 0 ? authProfiles.items.map((ap: any) => (
                <tr key={ap.id} className="border-b border-border/50 hover:bg-accent/50 cursor-pointer">
                  <td className="p-3 font-medium">{ap.name}</td>
                  <td className="p-3">{ap.vlan_id || ap.vlan_name || '-'}</td>
                  <td className="p-3">{ap.sgt_value ?? '-'}</td>
                  <td className="p-3">{ap.coa_action || '-'}</td>
                </tr>
              )) : <tr><td colSpan={4} className="p-6 text-center text-muted-foreground">No authorization profiles configured.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

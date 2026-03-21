import { useState } from 'react'

const STEPS = [
  { title: 'Welcome', desc: 'AI-assisted initial configuration' },
  { title: 'Network Scan', desc: 'Discover network devices and topology' },
  { title: 'Identity Sources', desc: 'Connect Active Directory, LDAP, or SAML' },
  { title: 'Network Design', desc: 'Describe your network in natural language' },
  { title: 'Policy Generation', desc: 'AI generates authentication & authorization policies' },
  { title: 'Review', desc: 'Review and adjust generated configuration' },
  { title: 'Activate', desc: 'Deploy configuration and run verification tests' },
]

export default function SetupWizardPage() {
  const [step, setStep] = useState(0)

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">NeuraNAC Setup Wizard</h1>
      <p className="text-muted-foreground mb-6">AI-assisted configuration in {STEPS.length} steps</p>

      <div className="flex gap-1 mb-8">
        {STEPS.map((_, i) => (
          <div key={i} className={`flex-1 h-1.5 rounded-full ${i <= step ? 'bg-primary' : 'bg-border'}`} />
        ))}
      </div>

      <div className="rounded-lg border border-border bg-card p-8 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center text-sm font-bold">{step + 1}</span>
          <div>
            <h2 className="text-lg font-semibold">{STEPS[step].title}</h2>
            <p className="text-sm text-muted-foreground">{STEPS[step].desc}</p>
          </div>
        </div>

        {step === 0 && (
          <div className="space-y-3 text-sm">
            <p>Welcome to the NeuraNAC Setup Wizard. This AI-assisted process will help you configure your network access control system.</p>
            <p className="text-muted-foreground">The wizard will scan your network, connect identity sources, generate policies from natural language descriptions, and activate the configuration.</p>
          </div>
        )}
        {step === 1 && (
          <div className="space-y-3">
            <label className="block text-sm text-muted-foreground">Subnet to scan</label>
            <input className="w-full px-3 py-2 rounded bg-background border border-border text-sm font-mono" placeholder="10.0.0.0/24" />
            <button className="px-4 py-2 bg-accent text-accent-foreground rounded-md text-sm">Start Scan</button>
          </div>
        )}
        {step === 2 && (
          <div className="space-y-3">
            <label className="block text-sm text-muted-foreground">Identity Source Type</label>
            <select className="w-full px-3 py-2 rounded bg-background border border-border text-sm">
              <option>Active Directory</option><option>LDAP</option><option>SAML</option><option>Internal Database</option>
            </select>
            <label className="block text-sm text-muted-foreground mt-2">Server Address</label>
            <input className="w-full px-3 py-2 rounded bg-background border border-border text-sm font-mono" placeholder="ldap://dc01.corp.local" />
          </div>
        )}
        {step === 3 && (
          <div className="space-y-3">
            <label className="block text-sm text-muted-foreground">Describe your network design in plain English</label>
            <textarea className="w-full px-3 py-2 rounded bg-background border border-border text-sm h-32" placeholder="We have employees on VLAN 10, guests on VLAN 20, and IoT devices on VLAN 30. Employees should use 802.1X with AD credentials. Guests get a captive portal. IoT devices use MAB." />
          </div>
        )}
        {step === 4 && (
          <div className="space-y-3 text-sm">
            <p>AI is generating policies based on your network description...</p>
            <div className="p-3 rounded bg-accent/30 text-muted-foreground">Generating policy sets, authorization profiles, and segmentation rules...</div>
          </div>
        )}
        {step === 5 && (
          <div className="space-y-3 text-sm">
            <p>Review the generated configuration before activation:</p>
            <div className="space-y-2">
              <div className="p-3 rounded bg-accent/30 flex justify-between"><span>Policy Sets</span><span className="font-bold">0 generated</span></div>
              <div className="p-3 rounded bg-accent/30 flex justify-between"><span>Auth Profiles</span><span className="font-bold">0 generated</span></div>
              <div className="p-3 rounded bg-accent/30 flex justify-between"><span>SGTs</span><span className="font-bold">0 generated</span></div>
            </div>
          </div>
        )}
        {step === 6 && (
          <div className="space-y-3 text-sm">
            <p>Ready to activate the configuration. This will push policies to the RADIUS server and enable authentication.</p>
            <button className="px-4 py-2 bg-green-600 text-white rounded-md text-sm hover:bg-green-700">Activate Configuration</button>
          </div>
        )}
      </div>

      <div className="flex justify-between">
        <button onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0} className="px-4 py-2 bg-accent text-accent-foreground rounded-md text-sm disabled:opacity-50">Back</button>
        <button onClick={() => setStep(Math.min(STEPS.length - 1, step + 1))} disabled={step === STEPS.length - 1} className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50">Next</button>
      </div>
    </div>
  )
}

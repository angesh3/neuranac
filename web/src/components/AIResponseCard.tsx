import { ChatMessage } from '@/lib/ai-store'
import { AlertTriangle, ArrowRight, Shield, Info } from 'lucide-react'

interface Props {
  message: ChatMessage
  onNavigate?: (route: string) => void
}

export default function AIResponseCard({ message, onNavigate }: Props) {
  const { type, data, route } = message

  // Navigation card
  if (type === 'navigation' && route) {
    return (
      <div className="flex items-center gap-3 p-3 rounded-xl glass-chip">
        <div className="w-8 h-8 rounded-lg bg-indigo-500/15 flex items-center justify-center flex-shrink-0">
          <ArrowRight className="h-4 w-4 text-indigo-400" />
        </div>
        <span className="text-sm text-foreground/85 flex-1">{message.content}</span>
        <button
          onClick={() => onNavigate?.(route)}
          className="text-xs px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-medium hover:shadow-lg hover:shadow-indigo-500/20 transition-all hover:scale-105"
        >
          Go
        </button>
      </div>
    )
  }

  // API result with table data
  if (type === 'api_result' && data) {
    const items = data?.items || data?.results || (Array.isArray(data) ? data : null)
    // Render table for list results
    if (items && Array.isArray(items) && items.length > 0) {
      const keys = Object.keys(items[0]).filter(
        (k) => !['tenant_id', 'created_at', 'updated_at', 'password_hash', 'shared_secret'].includes(k)
      ).slice(0, 6)

      return (
        <div className="space-y-3">
          <p className="text-sm text-foreground/85 leading-relaxed">{message.content}</p>
          <div className="rounded-xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ background: 'rgba(255,255,255,0.04)' }}>
                    {keys.map((k) => (
                      <th key={k} className="px-3 py-2.5 text-left font-medium text-muted-foreground/70 capitalize text-[11px] tracking-wide">
                        {k.replace(/_/g, ' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.slice(0, 20).map((item: any, i: number) => (
                    <tr key={i} className="border-t border-white/[0.04] hover:bg-white/[0.03] transition-colors">
                      {keys.map((k) => (
                        <td key={k} className="px-3 py-2 text-foreground/75 max-w-[200px] truncate">
                          {typeof item[k] === 'object' ? JSON.stringify(item[k]) : String(item[k] ?? '-')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {items.length > 20 && (
              <div className="px-3 py-2 text-[11px] text-muted-foreground/50" style={{ background: 'rgba(255,255,255,0.02)' }}>
                Showing 20 of {items.length} results
              </div>
            )}
          </div>
        </div>
      )
    }

    // Render single object result
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      const displayData = { ...data }
      delete displayData.items
      delete displayData.results
      const entries = Object.entries(displayData).filter(
        ([k]) => !['tenant_id', 'password_hash', 'shared_secret'].includes(k)
      ).slice(0, 12)

      if (entries.length > 0) {
        return (
          <div className="space-y-3">
            <p className="text-sm text-foreground/85 leading-relaxed">{message.content}</p>
            <div className="grid grid-cols-2 gap-1.5 rounded-xl p-3.5" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              {entries.map(([k, v]) => (
                <div key={k} className="flex items-start gap-2 py-1">
                  <span className="text-[11px] text-muted-foreground/50 capitalize min-w-[100px]">
                    {k.replace(/_/g, ' ')}:
                  </span>
                  <span className="text-xs font-medium text-foreground/80">
                    {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '-')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )
      }
    }
  }

  // Policy translation result
  if (type === 'policy_translation' && data) {
    const rules = data?.rules || []
    return (
      <div className="space-y-3">
        <p className="text-sm text-foreground/85 leading-relaxed">{message.content}</p>
        {rules.length > 0 && (
          <div className="space-y-1.5">
            {rules.map((rule: any, i: number) => (
              <div key={i} className="p-3 rounded-xl text-xs glass-lens" style={{ background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.12)' }}>
                <div className="flex items-center gap-2 mb-1">
                  <Shield className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="font-medium text-foreground/85">{rule.name || `Rule ${i + 1}`}</span>
                  <span className="ml-auto text-emerald-400 font-medium">{rule.action}</span>
                </div>
                {rule.conditions && (
                  <div className="text-muted-foreground/60 ml-5">
                    {rule.conditions.map((c: any, j: number) => (
                      <span key={j}>{c.attribute} {c.operator} {c.value} </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {data?.explanation && (
          <div className="flex items-start gap-2 p-3 rounded-xl text-xs" style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.12)' }}>
            <Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-blue-400" />
            <span className="text-blue-300/80">{data.explanation}</span>
          </div>
        )}
      </div>
    )
  }

  // Error card
  if (type === 'error') {
    return (
      <div className="flex items-start gap-3 p-3 rounded-xl" style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}>
        <AlertTriangle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
        <p className="text-sm text-red-300/80">{message.content}</p>
      </div>
    )
  }

  // Default text render (markdown-like)
  return (
    <div className="text-sm text-foreground/85 whitespace-pre-wrap leading-relaxed">
      {message.content.split('\n').map((line, i) => {
        if (line.startsWith('**') && line.endsWith('**')) {
          return <p key={i} className="font-semibold mt-2 mb-1 text-foreground/90">{line.replace(/\*\*/g, '')}</p>
        }
        if (line.startsWith('- ')) {
          const text = line.slice(2)
          const boldMatch = text.match(/^\*\*(.+?)\*\*(.*)/)
          if (boldMatch) {
            return (
              <p key={i} className="ml-3 py-0.5">
                <span className="text-violet-400/60 mr-1.5">•</span>
                <span className="font-medium text-foreground/90">{boldMatch[1]}</span>{boldMatch[2]}
              </p>
            )
          }
          return <p key={i} className="ml-3 py-0.5"><span className="text-violet-400/60 mr-1.5">•</span>{text}</p>
        }
        if (line.startsWith('# ')) {
          return <p key={i} className="text-base font-bold mt-3 mb-1 text-foreground/90">{line.slice(2)}</p>
        }
        if (line === '') return <br key={i} />
        return <p key={i}>{line}</p>
      })}
    </div>
  )
}

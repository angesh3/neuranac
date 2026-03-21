import { useAIStore } from '@/lib/ai-store'
import { Sparkles, LayoutDashboard } from 'lucide-react'

export default function AIModeToggle() {
  const aiMode = useAIStore((s) => s.aiMode)
  const toggleAIMode = useAIStore((s) => s.toggleAIMode)

  return (
    <button
      onClick={toggleAIMode}
      className="relative flex items-center w-[152px] h-9 rounded-full p-0.5 transition-all duration-300 glass-button"
      title={aiMode ? 'Switch to Dashboard' : 'Switch to AI Agent'}
    >
      {/* Sliding pill */}
      <div
        className={`absolute top-0.5 h-8 w-[74px] rounded-full transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] ${
          aiMode
            ? 'left-0.5 bg-gradient-to-r from-violet-500 to-indigo-600 shadow-lg shadow-violet-500/25'
            : 'left-[76px] bg-gradient-to-r from-slate-500/80 to-slate-600/80 shadow-lg shadow-slate-500/15'
        }`}
      />
      {/* Agent label */}
      <div
        className={`relative z-10 flex items-center justify-center gap-1.5 w-[74px] h-8 text-[11px] font-semibold tracking-wide transition-colors duration-300 ${
          aiMode ? 'text-white' : 'text-muted-foreground/50'
        }`}
      >
        <Sparkles className="h-3 w-3" />
        <span>Agent</span>
      </div>
      {/* Dashboard label */}
      <div
        className={`relative z-10 flex items-center justify-center gap-1.5 w-[74px] h-8 text-[11px] font-semibold tracking-wide transition-colors duration-300 ${
          !aiMode ? 'text-white' : 'text-muted-foreground/50'
        }`}
      >
        <LayoutDashboard className="h-3 w-3" />
        <span>Dash</span>
      </div>
    </button>
  )
}

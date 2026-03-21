/**
 * Glass-morphic skeleton loading components for the Liquid Glass design system.
 * Shows shimmering glass panels while AI is thinking.
 */

export function GlassSkeletonLine({ className = '' }: { className?: string }) {
  return <div className={`glass-skeleton h-4 ${className}`} />
}

export function GlassSkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`glass-skeleton ${className}`} />
}

export function GlassThinkingIndicator() {
  return (
    <div className="flex items-center gap-3 px-5 py-4">
      <div className="flex items-center gap-1.5">
        <div
          className="w-2 h-2 rounded-full bg-violet-400"
          style={{ animation: 'typing-dot 1.4s ease-in-out infinite' }}
        />
        <div
          className="w-2 h-2 rounded-full bg-indigo-400"
          style={{ animation: 'typing-dot 1.4s ease-in-out 0.2s infinite' }}
        />
        <div
          className="w-2 h-2 rounded-full bg-cyan-400"
          style={{ animation: 'typing-dot 1.4s ease-in-out 0.4s infinite' }}
        />
      </div>
      <span className="text-sm text-muted-foreground/70">Thinking</span>
    </div>
  )
}

export function GlassResponseSkeleton() {
  return (
    <div className="space-y-3 px-5 py-4">
      <GlassSkeletonLine className="w-3/4 h-4" />
      <GlassSkeletonLine className="w-full h-4" />
      <GlassSkeletonLine className="w-2/3 h-4" />
      <div className="mt-4 grid grid-cols-2 gap-2">
        <GlassSkeletonBlock className="h-16 rounded-xl" />
        <GlassSkeletonBlock className="h-16 rounded-xl" />
      </div>
    </div>
  )
}

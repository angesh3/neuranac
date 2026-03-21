/**
 * Reusable skeleton loading components for page loading states.
 */

export function SkeletonLine({ className = '' }: { className?: string }) {
  return <div className={`h-4 bg-muted animate-pulse rounded ${className}`} />
}

export function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`bg-muted animate-pulse rounded-lg ${className}`} />
}

export function CardSkeleton() {
  return (
    <div className="border border-border rounded-lg p-6 space-y-4">
      <SkeletonLine className="w-1/3 h-5" />
      <SkeletonLine className="w-2/3" />
      <SkeletonLine className="w-1/2" />
    </div>
  )
}

export function StatCardSkeleton() {
  return (
    <div className="border border-border rounded-lg p-4 space-y-2">
      <SkeletonLine className="w-1/2 h-3" />
      <SkeletonBlock className="w-2/3 h-8" />
      <SkeletonLine className="w-3/4 h-3" />
    </div>
  )
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-muted/50 px-4 py-3 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <SkeletonLine key={`h-${i}`} className="flex-1 h-3" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={`r-${r}`} className="px-4 py-3 flex gap-4 border-t border-border">
          {Array.from({ length: cols }).map((_, c) => (
            <SkeletonLine
              key={`r-${r}-c-${c}`}
              className={`flex-1 ${c === 0 ? 'w-1/4' : ''}`}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <SkeletonLine className="w-48 h-7" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatCardSkeleton key={i} />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SkeletonBlock className="h-64" />
        <SkeletonBlock className="h-64" />
      </div>
      <TableSkeleton rows={5} cols={5} />
    </div>
  )
}

export function PageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SkeletonLine className="w-48 h-7" />
        <SkeletonBlock className="w-32 h-9" />
      </div>
      <TableSkeleton rows={8} cols={5} />
    </div>
  )
}

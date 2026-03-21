import { memo } from 'react'

/**
 * Full-viewport animated gradient background with drifting color orbs.
 * Renders behind all content via position:fixed + z-index:-1.
 * Uses CSS animations defined in index.css for performance (GPU-composited).
 */
function LiquidGlassBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      {/* Base dark gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#0a0a1a] via-[#0d1117] to-[#0a0a1a]" />

      {/* Orb 1 — Indigo, top-left */}
      <div
        className="gradient-orb"
        style={{
          width: '45vw',
          height: '45vw',
          maxWidth: '600px',
          maxHeight: '600px',
          background: 'radial-gradient(circle, var(--orb-1) 0%, transparent 70%)',
          top: '-10%',
          left: '-5%',
          animation: 'orb-drift-1 25s ease-in-out infinite, pulse-glow 8s ease-in-out infinite',
        }}
      />

      {/* Orb 2 — Violet, center-right */}
      <div
        className="gradient-orb"
        style={{
          width: '40vw',
          height: '40vw',
          maxWidth: '500px',
          maxHeight: '500px',
          background: 'radial-gradient(circle, var(--orb-2) 0%, transparent 70%)',
          top: '20%',
          right: '-8%',
          animation: 'orb-drift-2 30s ease-in-out infinite, pulse-glow 10s ease-in-out infinite 2s',
        }}
      />

      {/* Orb 3 — Cyan, bottom-left */}
      <div
        className="gradient-orb"
        style={{
          width: '35vw',
          height: '35vw',
          maxWidth: '450px',
          maxHeight: '450px',
          background: 'radial-gradient(circle, var(--orb-3) 0%, transparent 70%)',
          bottom: '-5%',
          left: '15%',
          animation: 'orb-drift-3 22s ease-in-out infinite, pulse-glow 9s ease-in-out infinite 4s',
          opacity: 0.35,
        }}
      />

      {/* Orb 4 — Pink, bottom-right */}
      <div
        className="gradient-orb"
        style={{
          width: '30vw',
          height: '30vw',
          maxWidth: '400px',
          maxHeight: '400px',
          background: 'radial-gradient(circle, var(--orb-4) 0%, transparent 70%)',
          bottom: '10%',
          right: '10%',
          animation: 'orb-drift-4 28s ease-in-out infinite, pulse-glow 7s ease-in-out infinite 1s',
          opacity: 0.3,
        }}
      />

      {/* Orb 5 — Blue, center */}
      <div
        className="gradient-orb"
        style={{
          width: '25vw',
          height: '25vw',
          maxWidth: '350px',
          maxHeight: '350px',
          background: 'radial-gradient(circle, var(--orb-5) 0%, transparent 70%)',
          top: '40%',
          left: '40%',
          animation: 'orb-drift-1 35s ease-in-out infinite reverse, pulse-glow 12s ease-in-out infinite 3s',
          opacity: 0.25,
        }}
      />

      {/* Noise overlay for texture */}
      <div
        className="absolute inset-0 opacity-[0.015]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'repeat',
        }}
      />
    </div>
  )
}

export default memo(LiquidGlassBackground)

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/lib/store'
import LiquidGlassBackground from '@/components/LiquidGlassBackground'
import api from '@/lib/api'
import { Sparkles, ArrowRight } from 'lucide-react'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await api.post('/auth/login', { username, password })
      login(data.access_token, data.refresh_token, {
        id: '', username, tenantId: '', roles: ['admin'],
      })
      navigate('/')
    } catch {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden">
      <LiquidGlassBackground />

      <div className="relative z-10 w-full max-w-md space-y-8 px-4">
        {/* Logo */}
        <div className="text-center" style={{ animation: 'float-gentle 4s ease-in-out infinite' }}>
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 via-indigo-500 to-cyan-500 shadow-2xl shadow-violet-500/30 mb-4">
            <Sparkles className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-violet-300 via-indigo-300 to-cyan-300 bg-clip-text text-transparent">
            NeuraNAC
          </h1>
          <p className="text-muted-foreground/50 mt-1 text-sm">AI-Powered Network Access Control</p>
        </div>

        {/* Glass form */}
        <form
          onSubmit={handleSubmit}
          className="rounded-2xl p-8 space-y-5 glass-panel-solid glass-border"
        >
          <h2 className="text-lg font-semibold text-center text-foreground/85 tracking-tight">Sign in to continue</h2>

          {error && (
            <div className="rounded-xl p-3 text-sm text-red-300/80" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)' }}>
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-muted-foreground/60 tracking-wide uppercase">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-xl px-4 py-3 text-sm text-foreground/90 placeholder:text-muted-foreground/30 glass-input focus:outline-none"
              placeholder="Enter username"
              required
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-muted-foreground/60 tracking-wide uppercase">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl px-4 py-3 text-sm text-foreground/90 placeholder:text-muted-foreground/30 glass-input focus:outline-none"
              placeholder="Enter password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white bg-gradient-to-r from-violet-500 to-indigo-600 hover:from-violet-400 hover:to-indigo-500 shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 disabled:opacity-50 transition-all duration-200 hover:scale-[1.02] active:scale-100"
          >
            {loading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Signing in...
              </>
            ) : (
              <>
                Sign In
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        <p className="text-center text-[11px] text-muted-foreground/25">
          Protected by zero-trust authentication
        </p>
      </div>
    </div>
  )
}

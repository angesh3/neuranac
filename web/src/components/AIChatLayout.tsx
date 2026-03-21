import { useState, useRef, useEffect, useCallback, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAIStore, generateMsgId, ChatMessage } from '@/lib/ai-store'
import { useAuthStore } from '@/lib/store'
import AIResponseCard from '@/components/AIResponseCard'
import AIModeToggle from '@/components/AIModeToggle'
import LiquidGlassBackground from '@/components/LiquidGlassBackground'
import { GlassThinkingIndicator } from '@/components/GlassSkeleton'
import api from '@/lib/api'
import {
  Sparkles, Trash2, LogOut, ArrowUp,
  Shield, Network, Activity, Bot, Mic, Paperclip
} from 'lucide-react'

const WELCOME_SUGGESTIONS = [
  { label: 'Show system health', prompt: 'Show me the current system health status', icon: Activity },
  { label: 'Active sessions', prompt: 'Show all active RADIUS sessions', icon: Network },
  { label: 'Security posture', prompt: 'What is our current security posture?', icon: Shield },
  { label: 'What can you do?', prompt: 'What can you help me with?', icon: Bot },
]

export default function AIChatLayout() {
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [inputFocused, setInputFocused] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)

  const messages = useAIStore((s) => s.messages)
  const isLoading = useAIStore((s) => s.isLoading)
  const addMessage = useAIStore((s) => s.addMessage)
  const clearMessages = useAIStore((s) => s.clearMessages)
  const setLoading = useAIStore((s) => s.setLoading)
  const suggestions = useAIStore((s) => s.suggestions)
  const setSuggestions = useAIStore((s) => s.setSuggestions)
  const currentRoute = useAIStore((s) => s.currentRoute)

  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Load suggestions on mount
  useEffect(() => {
    loadSuggestions(currentRoute)
  }, [currentRoute])

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 160) + 'px'
    }
  }, [input])

  async function loadSuggestions(route: string) {
    try {
      const resp = await api.get(`/ai/suggestions?route=${encodeURIComponent(route)}`)
      setSuggestions(resp.data.suggestions || [])
    } catch {
      setSuggestions([
        { label: 'Show system status', prompt: 'Show system status' },
        { label: 'List endpoints', prompt: 'List all endpoints' },
        { label: 'Show sessions', prompt: 'Show all active sessions' },
        { label: 'Help', prompt: 'What can you help me with?' },
      ])
    }
  }

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return

    const userMsg: ChatMessage = {
      id: generateMsgId(),
      role: 'user',
      content: text.trim(),
      timestamp: Date.now(),
      type: 'text',
    }
    addMessage(userMsg)
    setInput('')
    setLoading(true)

    try {
      const resp = await api.post('/ai/chat', { message: text.trim(), context: { route: currentRoute } })
      const result = resp.data

      const assistantMsg: ChatMessage = {
        id: generateMsgId(),
        role: 'assistant',
        content: result.message || 'Done.',
        timestamp: Date.now(),
        type: result.type || 'text',
        intent: result.intent,
        data: result.data,
        route: result.route,
      }
      addMessage(assistantMsg)

      if (result.type === 'navigation' && result.route) {
        setTimeout(() => navigate(result.route), 600)
      }
    } catch (err: any) {
      addMessage({
        id: generateMsgId(),
        role: 'assistant',
        content: err?.response?.data?.message || 'Something went wrong. Please try again.',
        timestamp: Date.now(),
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }, [isLoading, currentRoute, addMessage, setLoading, navigate])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    sendMessage(input)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  function handleNavigate(route: string) {
    navigate(route)
  }

  const isEmpty = messages.length === 0

  return (
    <div className="relative flex flex-col h-screen overflow-hidden">
      <LiquidGlassBackground />

      {/* ─── Top Bar ─── */}
      <header className="relative z-10 flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
              <Sparkles className="h-4.5 w-4.5 text-white" />
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-400 rounded-full border-2 border-[#0d1117]" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-foreground/90 tracking-tight">NeuraNAC Agent</h1>
            <p className="text-[11px] text-muted-foreground/60">Network intelligence</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <AIModeToggle />
          <button
            onClick={clearMessages}
            className="glass-button p-2 rounded-xl text-muted-foreground/60 hover:text-foreground/80"
            title="Clear conversation"
          >
            <Trash2 className="h-4 w-4" />
          </button>
          <button
            onClick={logout}
            className="glass-button p-2 rounded-xl text-muted-foreground/60 hover:text-red-400"
            title="Logout"
          >
            <LogOut className="h-4 w-4" />
          </button>
          <div className="ml-2 w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-xs font-bold text-white uppercase">
            {user?.username?.[0] || 'A'}
          </div>
        </div>
      </header>

      {/* ─── Main Content Area ─── */}
      <div ref={scrollAreaRef} className="flex-1 overflow-y-auto relative z-10">
        {isEmpty ? (
          /* ─── Welcome / Landing Screen ─── */
          <div className="flex flex-col items-center justify-center h-full px-4 pb-32">
            {/* Animated logo */}
            <div className="mb-8 text-center" style={{ animation: 'float-gentle 4s ease-in-out infinite' }}>
              <div className="relative inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-violet-500 via-indigo-500 to-cyan-500 shadow-2xl shadow-violet-500/30 mb-6">
                <Sparkles className="h-10 w-10 text-white" />
                <div
                  className="absolute inset-0 rounded-3xl bg-gradient-to-br from-violet-400 via-indigo-400 to-cyan-400 opacity-0"
                  style={{ animation: 'border-glow 3s ease-in-out infinite' }}
                />
              </div>
              <h2 className="text-3xl font-bold text-foreground/90 mb-3 tracking-tight">
                Hi{user?.username ? `, ${user.username}` : ''}
              </h2>
              <p className="text-lg text-muted-foreground/60 max-w-lg leading-relaxed">
                I'm your NeuraNAC network intelligence agent. Ask me anything about
                your network — policies, sessions, devices, security, or troubleshooting.
              </p>
            </div>

            {/* Suggestion cards — Gemini style grid */}
            <div className="grid grid-cols-2 gap-3 max-w-xl w-full">
              {WELCOME_SUGGESTIONS.map((s, i) => {
                const Icon = s.icon
                return (
                  <button
                    key={i}
                    onClick={() => sendMessage(s.prompt)}
                    className="glass-chip glass-lens group rounded-2xl p-4 text-left flex flex-col gap-3 min-h-[88px]"
                    style={{ animationDelay: `${i * 0.08}s` }}
                  >
                    <Icon className="h-5 w-5 text-violet-400/70 group-hover:text-violet-300 transition-colors" />
                    <span className="text-sm text-foreground/80 group-hover:text-foreground/95 leading-snug transition-colors">
                      {s.label}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        ) : (
          /* ─── Chat Messages ─── */
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-1 pb-8">
            {messages.map((msg, idx) => (
              <div
                key={msg.id}
                className={`msg-enter flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                style={{ animationDelay: `${Math.min(idx * 0.02, 0.3)}s` }}
              >
                {msg.role === 'assistant' && (
                  <div className="flex-shrink-0 mr-3 mt-1">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500/80 to-indigo-600/80 flex items-center justify-center">
                      <Sparkles className="h-3.5 w-3.5 text-white" />
                    </div>
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'glass-panel-solid rounded-br-md text-foreground/90'
                      : ''
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <AIResponseCard message={msg} onNavigate={handleNavigate} />
                  ) : (
                    <p className="text-sm leading-relaxed">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}

            {/* Thinking indicator */}
            {isLoading && (
              <div className="msg-enter flex justify-start">
                <div className="flex-shrink-0 mr-3 mt-1">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500/80 to-indigo-600/80 flex items-center justify-center">
                    <Sparkles className="h-3.5 w-3.5 text-white" />
                  </div>
                </div>
                <div className="glass-panel rounded-2xl overflow-hidden">
                  <GlassThinkingIndicator />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* ─── Quick suggestions (when in conversation) ─── */}
      {!isEmpty && suggestions.length > 0 && !isLoading && (
        <div className="relative z-10 px-4 pb-2 max-w-3xl mx-auto w-full">
          <div className="flex flex-wrap gap-1.5 justify-center">
            {suggestions.slice(0, 4).map((s, i) => (
              <button
                key={i}
                onClick={() => sendMessage(s.prompt)}
                className="glass-chip rounded-full px-3.5 py-1.5 text-xs text-muted-foreground/70 hover:text-foreground/90"
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ─── Floating Input Bar ─── */}
      <div className={`relative z-10 px-4 ${isEmpty ? 'pb-8' : 'pb-5'} pt-2`}>
        <form
          onSubmit={handleSubmit}
          className={`max-w-3xl mx-auto relative transition-all duration-300 ${
            inputFocused ? 'scale-[1.01]' : ''
          }`}
        >
          <div className={`
            relative rounded-3xl overflow-hidden transition-all duration-300
            ${inputFocused
              ? 'shadow-[0_0_40px_rgba(99,102,241,0.15),0_8px_32px_rgba(0,0,0,0.4)]'
              : 'shadow-[0_8px_32px_rgba(0,0,0,0.3)]'
            }
          `}>
            {/* Glass background */}
            <div className="absolute inset-0 bg-[rgba(255,255,255,0.04)] backdrop-blur-xl border border-[rgba(255,255,255,0.08)] rounded-3xl" />

            {/* Refracted gradient border */}
            <div className="absolute inset-0 rounded-3xl pointer-events-none"
              style={{
                background: 'linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 40%, transparent 60%, rgba(0,0,0,0.15) 100%)',
                WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
                WebkitMaskComposite: 'xor',
                maskComposite: 'exclude',
                padding: '1px',
              }}
            />

            <div className="relative flex items-end gap-2 px-4 py-3">
              {/* Attachment button */}
              <button
                type="button"
                className="flex-shrink-0 p-2 rounded-xl text-muted-foreground/40 hover:text-muted-foreground/70 transition-colors mb-0.5"
                title="Attach file"
              >
                <Paperclip className="h-5 w-5" />
              </button>

              {/* Textarea */}
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)}
                placeholder={isEmpty
                  ? "Ask me anything about your network..."
                  : "Message NeuraNAC Agent..."
                }
                className="flex-1 bg-transparent text-foreground/90 text-sm placeholder:text-muted-foreground/40 resize-none focus:outline-none min-h-[24px] max-h-[160px] py-1.5 leading-relaxed"
                rows={1}
                disabled={isLoading}
                autoFocus
              />

              {/* Voice button */}
              <button
                type="button"
                className="flex-shrink-0 p-2 rounded-xl text-muted-foreground/40 hover:text-muted-foreground/70 transition-colors mb-0.5"
                title="Voice input"
              >
                <Mic className="h-5 w-5" />
              </button>

              {/* Send button */}
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className={`
                  flex-shrink-0 p-2.5 rounded-xl transition-all duration-200 mb-0.5
                  ${input.trim()
                    ? 'bg-gradient-to-r from-violet-500 to-indigo-600 text-white shadow-lg shadow-violet-500/25 hover:shadow-violet-500/40 hover:scale-105'
                    : 'bg-white/5 text-muted-foreground/30'
                  }
                `}
              >
                <ArrowUp className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Disclaimer */}
          <p className="text-center text-[10px] text-muted-foreground/30 mt-2">
            NeuraNAC Agent can make mistakes. Verify critical network changes.
          </p>
        </form>
      </div>
    </div>
  )
}

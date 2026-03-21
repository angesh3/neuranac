import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  type?: 'text' | 'api_result' | 'navigation' | 'policy_translation' | 'error'
  intent?: string
  data?: any
  route?: string
}

interface AIState {
  // Mode toggle
  aiMode: boolean
  toggleAIMode: () => void
  setAIMode: (mode: boolean) => void

  // Chat state
  messages: ChatMessage[]
  isLoading: boolean
  addMessage: (msg: ChatMessage) => void
  clearMessages: () => void
  setLoading: (loading: boolean) => void

  // Suggestions
  suggestions: { label: string; prompt: string }[]
  setSuggestions: (s: { label: string; prompt: string }[]) => void

  // Current context
  currentRoute: string
  setCurrentRoute: (route: string) => void
}

let _msgCounter = 0
export function generateMsgId(): string {
  _msgCounter += 1
  return `msg-${Date.now()}-${_msgCounter}`
}

export const useAIStore = create<AIState>()(
  persist(
    (set) => ({
      // Default to AI mode on
      aiMode: true,
      toggleAIMode: () => set((s) => ({ aiMode: !s.aiMode })),
      setAIMode: (mode) => set({ aiMode: mode }),

      messages: [],
      isLoading: false,
      addMessage: (msg) =>
        set((s) => ({ messages: [...s.messages.slice(-200), msg] })),
      clearMessages: () => set({ messages: [] }),
      setLoading: (loading) => set({ isLoading: loading }),

      suggestions: [],
      setSuggestions: (s) => set({ suggestions: s }),

      currentRoute: '/',
      setCurrentRoute: (route) => set({ currentRoute: route }),
    }),
    {
      name: 'neuranac-ai-mode',
      partialize: (state) => ({
        aiMode: state.aiMode,
        messages: state.messages.slice(-50),
      }),
    }
  )
)

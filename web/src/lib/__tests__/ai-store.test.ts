import { describe, it, expect, beforeEach } from 'vitest'
import { useAIStore, generateMsgId, type ChatMessage } from '../ai-store'

describe('useAIStore', () => {
  beforeEach(() => {
    useAIStore.setState({
      aiMode: true,
      messages: [],
      isLoading: false,
      suggestions: [],
      currentRoute: '/',
    })
  })

  it('defaults to AI mode on', () => {
    expect(useAIStore.getState().aiMode).toBe(true)
  })

  it('toggleAIMode flips mode', () => {
    useAIStore.getState().toggleAIMode()
    expect(useAIStore.getState().aiMode).toBe(false)
    useAIStore.getState().toggleAIMode()
    expect(useAIStore.getState().aiMode).toBe(true)
  })

  it('setAIMode sets explicit value', () => {
    useAIStore.getState().setAIMode(false)
    expect(useAIStore.getState().aiMode).toBe(false)
  })

  it('addMessage appends to messages', () => {
    const msg: ChatMessage = {
      id: 'msg-1',
      role: 'user',
      content: 'hello',
      timestamp: Date.now(),
    }
    useAIStore.getState().addMessage(msg)
    expect(useAIStore.getState().messages).toHaveLength(1)
    expect(useAIStore.getState().messages[0].content).toBe('hello')
  })

  it('clearMessages empties messages', () => {
    useAIStore.getState().addMessage({
      id: 'msg-1', role: 'user', content: 'hi', timestamp: Date.now(),
    })
    useAIStore.getState().clearMessages()
    expect(useAIStore.getState().messages).toHaveLength(0)
  })

  it('setLoading controls loading state', () => {
    useAIStore.getState().setLoading(true)
    expect(useAIStore.getState().isLoading).toBe(true)
    useAIStore.getState().setLoading(false)
    expect(useAIStore.getState().isLoading).toBe(false)
  })

  it('setSuggestions updates suggestions', () => {
    const sugs = [{ label: 'Show endpoints', prompt: 'list endpoints' }]
    useAIStore.getState().setSuggestions(sugs)
    expect(useAIStore.getState().suggestions).toEqual(sugs)
  })

  it('setCurrentRoute updates route', () => {
    useAIStore.getState().setCurrentRoute('/policies')
    expect(useAIStore.getState().currentRoute).toBe('/policies')
  })
})

describe('generateMsgId', () => {
  it('returns unique IDs', () => {
    const a = generateMsgId()
    const b = generateMsgId()
    expect(a).not.toBe(b)
    expect(a).toMatch(/^msg-/)
  })
})

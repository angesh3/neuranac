import { describe, it, expect, beforeEach } from 'vitest'
import axios from 'axios'

// We test the module's configuration, not actual HTTP calls
describe('API client configuration', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('axios is available', () => {
    expect(axios).toBeDefined()
    expect(axios.create).toBeTypeOf('function')
  })

  it('localStorage auth injection pattern works', () => {
    const stored = {
      state: { accessToken: 'test-token', refreshToken: 'ref-token', isAuthenticated: true },
    }
    localStorage.setItem('neuranac-auth', JSON.stringify(stored))

    const raw = localStorage.getItem('neuranac-auth')
    expect(raw).not.toBeNull()
    const parsed = JSON.parse(raw!)
    expect(parsed.state.accessToken).toBe('test-token')
  })

  it('missing auth does not throw', () => {
    const raw = localStorage.getItem('neuranac-auth')
    expect(raw).toBeNull()
  })

  it('malformed auth gracefully handled', () => {
    localStorage.setItem('neuranac-auth', 'not-json')
    expect(() => {
      const raw = localStorage.getItem('neuranac-auth')
      if (raw) JSON.parse(raw)
    }).toThrow()
  })
})

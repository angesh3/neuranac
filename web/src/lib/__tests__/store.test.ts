import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from '../store'

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.setState({
      isAuthenticated: false,
      accessToken: null,
      refreshToken: null,
      user: null,
    })
  })

  it('starts unauthenticated', () => {
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.accessToken).toBeNull()
    expect(state.user).toBeNull()
  })

  it('login sets auth state', () => {
    const user = { id: 'u1', username: 'admin', tenantId: 't1', roles: ['admin'] }
    useAuthStore.getState().login('access-tok', 'refresh-tok', user)

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.accessToken).toBe('access-tok')
    expect(state.refreshToken).toBe('refresh-tok')
    expect(state.user?.username).toBe('admin')
  })

  it('logout clears auth state', () => {
    const user = { id: 'u1', username: 'admin', tenantId: 't1', roles: ['admin'] }
    useAuthStore.getState().login('access-tok', 'refresh-tok', user)
    useAuthStore.getState().logout()

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.accessToken).toBeNull()
    expect(state.refreshToken).toBeNull()
    expect(state.user).toBeNull()
  })
})

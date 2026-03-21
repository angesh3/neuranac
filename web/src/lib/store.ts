import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  isAuthenticated: boolean
  accessToken: string | null
  refreshToken: string | null
  user: { id: string; username: string; tenantId: string; roles: string[] } | null
  login: (accessToken: string, refreshToken: string, user: AuthState['user']) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      accessToken: null,
      refreshToken: null,
      user: null,
      login: (accessToken, refreshToken, user) =>
        set({ isAuthenticated: true, accessToken, refreshToken, user }),
      logout: () =>
        set({ isAuthenticated: false, accessToken: null, refreshToken: null, user: null }),
    }),
    { name: 'neuranac-auth' }
  )
)

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const stored = localStorage.getItem('neuranac-auth')
  if (stored) {
    const { state } = JSON.parse(stored)
    if (state?.accessToken) {
      config.headers.Authorization = `Bearer ${state.accessToken}`
    }
  }
  // Attach X-NeuraNAC-Site header for cross-site federation
  const siteStored = localStorage.getItem('neuranac-site')
  if (siteStored) {
    try {
      const { state } = JSON.parse(siteStored)
      if (state?.selectedSite && state.selectedSite !== 'local') {
        config.headers['X-NeuraNAC-Site'] = state.selectedSite
      }
    } catch {}
  }
  return config
})

// --- Token refresh interceptor ---
let isRefreshing = false
let failedQueue: { resolve: (token: string) => void; reject: (err: unknown) => void }[] = []

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((p) => {
    if (token) p.resolve(token)
    else p.reject(error)
  })
  failedQueue = []
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // Only attempt refresh on 401, and not on the refresh endpoint itself
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/refresh') &&
      !originalRequest.url?.includes('/auth/login')
    ) {
      if (isRefreshing) {
        // Queue this request until the refresh completes
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`
              resolve(api(originalRequest))
            },
            reject: (err: unknown) => reject(err),
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const stored = localStorage.getItem('neuranac-auth')
        const refreshToken = stored ? JSON.parse(stored)?.state?.refreshToken : null

        if (!refreshToken) {
          throw new Error('No refresh token')
        }

        const { data } = await axios.post('/api/v1/auth/refresh', {
          refresh_token: refreshToken,
        })

        const newAccess = data.access_token
        const newRefresh = data.refresh_token || refreshToken

        // Update Zustand persisted store in localStorage
        if (stored) {
          const parsed = JSON.parse(stored)
          parsed.state.accessToken = newAccess
          parsed.state.refreshToken = newRefresh
          localStorage.setItem('neuranac-auth', JSON.stringify(parsed))
        }

        originalRequest.headers.Authorization = `Bearer ${newAccess}`
        processQueue(null, newAccess)
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        localStorage.removeItem('neuranac-auth')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Non-401 errors or login/refresh failures — pass through
    if (error.response?.status === 401) {
      localStorage.removeItem('neuranac-auth')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

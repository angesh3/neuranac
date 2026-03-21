import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '@/lib/api'

export interface UIConfig {
  deploymentMode: 'standalone' | 'hybrid'
  siteType: 'onprem' | 'cloud'
  siteId: string
  siteName: string
  legacyNacEnabled: boolean
  peerConfigured: boolean
  peerApiUrl: string | null
  peerSiteId: string | null
  peerSiteName: string | null
  connectorConfigured: boolean
  connectorUrl: string | null
  nodeId: string
  environment: string
}

export type SiteFilter = 'local' | 'peer' | 'all'

interface SiteState {
  // UI config fetched from backend
  config: UIConfig | null
  configLoaded: boolean
  configError: string | null

  // User selection for cross-site filtering
  selectedSite: SiteFilter

  // Actions
  fetchConfig: () => Promise<void>
  setSelectedSite: (site: SiteFilter) => void

  // Computed helpers
  isHybrid: () => boolean
  isLegacyNacEnabled: () => boolean
  getSiteHeader: () => string
}

export const useSiteStore = create<SiteState>()(
  persist(
    (set, get) => ({
      config: null,
      configLoaded: false,
      configError: null,
      selectedSite: 'local',

      fetchConfig: async () => {
        try {
          const { data } = await api.get('/config/ui')
          set({ config: data, configLoaded: true, configError: null })
          // Reset to 'local' if standalone mode
          if (data.deploymentMode === 'standalone') {
            set({ selectedSite: 'local' })
          }
        } catch (err: any) {
          set({
            configError: err?.message || 'Failed to fetch UI config',
            configLoaded: true,
          })
        }
      },

      setSelectedSite: (site) => {
        const config = get().config
        // Only allow peer/all in hybrid mode
        if (!config || config.deploymentMode === 'standalone') {
          set({ selectedSite: 'local' })
          return
        }
        set({ selectedSite: site })
      },

      isHybrid: () => get().config?.deploymentMode === 'hybrid',
      isLegacyNacEnabled: () => get().config?.legacyNacEnabled === true,

      getSiteHeader: () => {
        const { selectedSite, config } = get()
        if (!config || config.deploymentMode === 'standalone') return 'local'
        return selectedSite
      },
    }),
    {
      name: 'neuranac-site',
      partialize: (state) => ({ selectedSite: state.selectedSite }),
    }
  )
)

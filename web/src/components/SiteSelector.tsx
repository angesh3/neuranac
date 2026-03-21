import { useEffect } from 'react'
import { useSiteStore, SiteFilter } from '@/lib/site-store'
import { Globe, Server, Layers, Wifi, WifiOff } from 'lucide-react'

const siteOptions: { value: SiteFilter; label: string; icon: React.ElementType }[] = [
  { value: 'local', label: 'Local', icon: Server },
  { value: 'peer', label: 'Peer', icon: Globe },
  { value: 'all', label: 'All Sites', icon: Layers },
]

export default function SiteSelector() {
  const { config, configLoaded, selectedSite, setSelectedSite, fetchConfig } = useSiteStore()

  useEffect(() => {
    if (!configLoaded) {
      fetchConfig()
    }
  }, [configLoaded, fetchConfig])

  // Hidden in standalone mode or if config not loaded
  if (!configLoaded || !config || config.deploymentMode === 'standalone') {
    return null
  }

  const connectorOk = config.connectorConfigured
  const siteTypeLabel = config.siteType === 'onprem' ? 'On-Prem' : 'Cloud'

  return (
    <div className="flex items-center gap-2">
      {/* Connector status dot (only if NeuraNAC enabled) */}
      {config.legacyNacEnabled && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground" title={connectorOk ? 'Bridge Connector connected' : 'Bridge Connector disconnected'}>
          {connectorOk ? (
            <Wifi className="h-3 w-3 text-green-500" />
          ) : (
            <WifiOff className="h-3 w-3 text-orange-400" />
          )}
          <span className="hidden sm:inline">NeuraNAC</span>
        </div>
      )}

      {/* Site type badge */}
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
        config.siteType === 'onprem'
          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
          : 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
      }`}>
        {siteTypeLabel}
      </span>

      {/* Site selector pill */}
      <div className="flex items-center bg-muted rounded-lg p-0.5 gap-0.5">
        {siteOptions.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            onClick={() => setSelectedSite(value)}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              selectedSite === value
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Icon className="h-3 w-3" />
            {label}
          </button>
        ))}
      </div>

      {/* Peer site name */}
      {config.peerSiteName && (
        <span className="text-xs text-muted-foreground hidden lg:inline">
          Peer: {config.peerSiteName}
        </span>
      )}
    </div>
  )
}

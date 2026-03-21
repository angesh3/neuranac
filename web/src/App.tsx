import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/lib/store'
import { useAIStore } from '@/lib/ai-store'
import ErrorBoundary from '@/components/ErrorBoundary'
import Layout from '@/components/Layout'
import AIChatLayout from '@/components/AIChatLayout'

// Lazy-loaded pages — each becomes a separate chunk for optimal initial load
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const PoliciesPage = lazy(() => import('@/pages/PoliciesPage'))
const NetworkDevicesPage = lazy(() => import('@/pages/NetworkDevicesPage'))
const EndpointsPage = lazy(() => import('@/pages/EndpointsPage'))
const SessionsPage = lazy(() => import('@/pages/SessionsPage'))
const IdentityPage = lazy(() => import('@/pages/IdentityPage'))
const CertificatesPage = lazy(() => import('@/pages/CertificatesPage'))
const SegmentationPage = lazy(() => import('@/pages/SegmentationPage'))
const GuestPage = lazy(() => import('@/pages/GuestPage'))
const PosturePage = lazy(() => import('@/pages/PosturePage'))
const AIAgentsPage = lazy(() => import('@/pages/AIAgentsPage'))
const AIDataFlowPage = lazy(() => import('@/pages/AIDataFlowPage'))
const ShadowAIPage = lazy(() => import('@/pages/ShadowAIPage'))
const NodesPage = lazy(() => import('@/pages/NodesPage'))
const AuditPage = lazy(() => import('@/pages/AuditPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const SetupWizardPage = lazy(() => import('@/pages/SetupWizardPage'))
const DiagnosticsPage = lazy(() => import('@/pages/DiagnosticsPage'))
const PrivacyPage = lazy(() => import('@/pages/PrivacyPage'))
const HelpDocsPage = lazy(() => import('@/pages/HelpDocsPage'))
const AIHelpPage = lazy(() => import('@/pages/AIHelpPage'))
const SIEMPage = lazy(() => import('@/pages/SIEMPage'))
const WebhooksPage = lazy(() => import('@/pages/WebhooksPage'))
const LicensesPage = lazy(() => import('@/pages/LicensesPage'))
const TopologyPage = lazy(() => import('@/pages/TopologyPage'))
const SiteManagementPage = lazy(() => import('@/pages/SiteManagementPage'))
const OnPremSetupWizardPage = lazy(() => import('@/pages/OnPremSetupWizardPage'))

function PageLoader() {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-4">
      <div className="relative w-10 h-10">
        <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-violet-500/30 to-indigo-600/30 animate-ping" />
        <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
          <svg className="w-5 h-5 text-white animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      </div>
      <div className="glass-skeleton w-32 h-3 rounded-full" />
    </div>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function ClassicRoutes() {
  return (
    <Layout>
      <ErrorBoundary>
        <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/topology" element={<TopologyPage />} />
          <Route path="/policies" element={<PoliciesPage />} />
          <Route path="/network-devices" element={<NetworkDevicesPage />} />
          <Route path="/endpoints" element={<EndpointsPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/identity" element={<IdentityPage />} />
          <Route path="/certificates" element={<CertificatesPage />} />
          <Route path="/segmentation" element={<SegmentationPage />} />
          <Route path="/guest" element={<GuestPage />} />
          <Route path="/posture" element={<PosturePage />} />
          <Route path="/ai/agents" element={<AIAgentsPage />} />
          <Route path="/ai/data-flow" element={<AIDataFlowPage />} />
          <Route path="/ai/shadow" element={<ShadowAIPage />} />
          <Route path="/nodes" element={<NodesPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/diagnostics" element={<DiagnosticsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/help/docs" element={<HelpDocsPage />} />
          <Route path="/help/ai" element={<AIHelpPage />} />
          <Route path="/siem" element={<SIEMPage />} />
          <Route path="/webhooks" element={<WebhooksPage />} />
          <Route path="/licenses" element={<LicensesPage />} />
          <Route path="/sites" element={<SiteManagementPage />} />
          <Route path="/sites/onprem-setup" element={<OnPremSetupWizardPage />} />
        </Routes>
        </Suspense>
      </ErrorBoundary>
    </Layout>
  )
}

function AppShell() {
  const aiMode = useAIStore((s) => s.aiMode)
  return (
    <ErrorBoundary>
      {aiMode ? <AIChatLayout /> : <ClassicRoutes />}
    </ErrorBoundary>
  )
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/setup" element={<SetupWizardPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        />
      </Routes>
    </Suspense>
  )
}

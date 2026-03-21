import { Link, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/lib/store'
import {
  LayoutDashboard, Shield, Router, Monitor, Activity, UserCheck, Lock,
  Network, Users, ClipboardCheck, Bot, ArrowLeftRight, Eye, Server,
  FileText, Settings, LogOut, Brain, Wrench, HelpCircle, MessageSquare, Bell, Key,
  ShieldCheck, Map, Layers
} from 'lucide-react'
import ToastContainer from '@/components/ToastContainer'
import SiteSelector from '@/components/SiteSelector'
import AIModeToggle from '@/components/AIModeToggle'

interface NavItem {
  label: string
  path: string
  icon: React.ElementType
}

const mainNav: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard },
  { label: 'Topology', path: '/topology', icon: Map },
  { label: 'Policies', path: '/policies', icon: Shield },
  { label: 'Network Devices', path: '/network-devices', icon: Router },
  { label: 'Endpoints', path: '/endpoints', icon: Monitor },
  { label: 'Sessions', path: '/sessions', icon: Activity },
  { label: 'Identity Sources', path: '/identity', icon: UserCheck },
  { label: 'Certificates', path: '/certificates', icon: Lock },
  { label: 'Segmentation', path: '/segmentation', icon: Network },
  { label: 'Guest & BYOD', path: '/guest', icon: Users },
  { label: 'Posture', path: '/posture', icon: ClipboardCheck },
  { label: 'AI Agents', path: '/ai/agents', icon: Bot },
  { label: 'AI Data Flow', path: '/ai/data-flow', icon: ArrowLeftRight },
  { label: 'Shadow AI', path: '/ai/shadow', icon: Eye },
]

const bottomNav: NavItem[] = [
  { label: 'Site Management', path: '/sites', icon: Layers },
  { label: 'SIEM', path: '/siem', icon: ShieldCheck },
  { label: 'Webhooks', path: '/webhooks', icon: Bell },
  { label: 'Licenses', path: '/licenses', icon: Key },
  { label: 'Twin Nodes', path: '/nodes', icon: Server },
  { label: 'Audit Log', path: '/audit', icon: FileText },
  { label: 'Diagnostics', path: '/diagnostics', icon: Wrench },
  { label: 'Settings', path: '/settings', icon: Settings },
  { label: 'Help Docs', path: '/help/docs', icon: HelpCircle },
  { label: 'AI Assistant', path: '/help/ai', icon: MessageSquare },
]

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon
  return (
    <Link
      to={item.path}
      className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm mb-0.5 transition-colors ${
        active
          ? 'bg-primary/10 text-primary font-medium'
          : 'text-muted-foreground hover:bg-accent hover:text-foreground'
      }`}
    >
      <Icon className="h-4 w-4" />
      {item.label}
    </Link>
  )
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)

  return (
    <div className="flex h-screen bg-background">
      <ToastContainer />
      <aside className="w-64 border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Brain className="h-8 w-8 text-primary" />
            <div>
              <h1 className="text-lg font-bold text-foreground">NeuraNAC</h1>
              <p className="text-xs text-muted-foreground">AI-Powered Network Access Control</p>
            </div>
          </div>
          <div className="mt-2">
            <SiteSelector />
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto p-2">
          {mainNav.map((item) => (
            <NavLink key={item.path} item={item} active={location.pathname === item.path} />
          ))}

          {bottomNav.map((item) => (
            <NavLink key={item.path} item={item} active={location.pathname === item.path} />
          ))}
        </nav>
        <div className="p-3 border-t border-border space-y-3">
          <div className="flex justify-center">
            <AIModeToggle />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">{user?.username || 'admin'}</span>
            <button onClick={logout} className="text-muted-foreground hover:text-destructive">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  )
}

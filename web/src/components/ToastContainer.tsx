import { useToastStore, type Toast } from '@/lib/toast-store'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
  warning: AlertTriangle,
}

const colorMap = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
}

const iconColorMap = {
  success: 'text-green-500',
  error: 'text-red-500',
  info: 'text-blue-500',
  warning: 'text-yellow-500',
}

function ToastItem({ toast }: { toast: Toast }) {
  const removeToast = useToastStore((s) => s.removeToast)
  const Icon = iconMap[toast.type]

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg animate-in slide-in-from-right ${colorMap[toast.type]}`}
    >
      <Icon className={`h-5 w-5 mt-0.5 flex-shrink-0 ${iconColorMap[toast.type]}`} />
      <p className="text-sm flex-1">{toast.message}</p>
      <button
        onClick={() => removeToast(toast.id)}
        className="flex-shrink-0 hover:opacity-70 transition-opacity"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts)

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  )
}

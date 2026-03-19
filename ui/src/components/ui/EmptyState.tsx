import { Rss } from 'lucide-react'
import { Link } from 'react-router-dom'

interface EmptyStateProps {
  title: string
  description: string
  action?: { label: string; to: string }
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 rounded-full bg-orange-50 p-4">
        <Rss className="h-8 w-8 text-orange-400" />
      </div>
      <h3 className="mb-1 text-lg font-semibold text-gray-800">{title}</h3>
      <p className="mb-6 max-w-sm text-sm text-gray-500">{description}</p>
      {action && (
        <Link
          to={action.to}
          className="inline-flex items-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 text-sm"
        >
          {action.label}
        </Link>
      )}
    </div>
  )
}

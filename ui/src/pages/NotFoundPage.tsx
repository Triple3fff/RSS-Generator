import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center py-24 text-center">
      <p className="text-5xl font-bold text-gray-200">404</p>
      <p className="mt-2 text-lg font-medium text-gray-600">Page not found</p>
      <Link to="/" className="mt-6 text-sm text-orange-500 hover:underline">
        Back to Dashboard
      </Link>
    </div>
  )
}

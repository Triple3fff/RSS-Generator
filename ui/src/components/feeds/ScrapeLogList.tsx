import { CheckCircle, XCircle } from 'lucide-react'
import type { ScrapeLog } from '../../api/types'
import { Badge } from '../ui/Badge'
import { formatDateTime } from '../../lib/dates'

export function ScrapeLogList({ logs }: { logs: ScrapeLog[] }) {
  if (logs.length === 0) {
    return <p className="py-6 text-center text-sm text-gray-400">No scrape history yet.</p>
  }

  return (
    <ul className="divide-y divide-gray-100">
      {logs.map((log) => (
        <li key={log.id} className="flex items-start gap-3 py-3">
          {log.success ? (
            <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-500" />
          ) : (
            <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-gray-500">{formatDateTime(log.scraped_at)}</span>
              {log.duration_ms != null && (
                <span className="text-gray-400">{log.duration_ms}ms</span>
              )}
              {log.new_items > 0 && <Badge color="green">+{log.new_items} new</Badge>}
              {log.updated_items > 0 && <Badge color="blue">{log.updated_items} updated</Badge>}
              {log.unchanged_items > 0 && (
                <Badge color="gray">{log.unchanged_items} unchanged</Badge>
              )}
            </div>
            {log.error_message && (
              <p className="mt-1 truncate text-xs text-red-500">{log.error_message}</p>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

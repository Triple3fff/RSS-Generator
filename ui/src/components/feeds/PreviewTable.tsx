import type { RawItem } from '../../api/types'
import { formatDateTime } from '../../lib/dates'

interface PreviewTableProps {
  items: RawItem[]
}

export function PreviewTable({ items }: PreviewTableProps) {
  if (items.length === 0) {
    return (
      <p className="rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-700">
        Selectors matched 0 items. Check your CSS selectors and try again.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-md border border-gray-200">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th className="px-4 py-2 text-left font-medium">Title</th>
            <th className="px-4 py-2 text-left font-medium">Description</th>
            <th className="px-4 py-2 text-left font-medium">Author</th>
            <th className="px-4 py-2 text-left font-medium">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {items.map((item, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="max-w-xs px-4 py-3">
                {item.link ? (
                  <a
                    href={item.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="line-clamp-2 font-medium text-orange-600 hover:underline"
                  >
                    {item.title ?? '(no title)'}
                  </a>
                ) : (
                  <span className="line-clamp-2 font-medium text-gray-700">
                    {item.title ?? '(no title)'}
                  </span>
                )}
              </td>
              <td className="max-w-sm px-4 py-3">
                {item.description ? (
                  <span className="line-clamp-2 text-gray-600">{item.description}</span>
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-gray-500">
                {item.author ?? '—'}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-gray-500">
                {item.pub_date ? formatDateTime(item.pub_date) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

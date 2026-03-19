import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { feedsApi } from '../../api/feeds'
import { getRssUrl } from '../../lib/rssUrl'

export function RssUrlCopy({ slug }: { slug: string }) {
  const [copied, setCopied] = useState(false)
  const { data: config } = useQuery({
    queryKey: ['server-config'],
    queryFn: feedsApi.getConfig,
    staleTime: Infinity,
  })

  const url = getRssUrl(slug, config?.public_base_url)

  const copy = () => {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="flex items-center gap-2 rounded-md border border-orange-200 bg-orange-50 px-3 py-2">
      <span className="flex-1 truncate font-mono text-xs text-orange-700">{url}</span>
      <button
        onClick={copy}
        title="Copy RSS URL"
        className="flex-shrink-0 text-orange-500 hover:text-orange-700 transition-colors"
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </button>
    </div>
  )
}

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PlusCircle, RefreshCw, Trash2, Pencil, ExternalLink } from 'lucide-react'
import { PageHeader } from '../components/layout/PageHeader'
import { FeedStatusBadge } from '../components/feeds/FeedStatusBadge'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { useFeedList, useDeleteFeed, useTriggerScrape } from '../hooks/useFeeds'
import { formatRelative } from '../lib/dates'
import type { FeedConfig } from '../api/types'

export function FeedListPage() {
  const { data: feeds, isLoading } = useFeedList()
  const deleteMutation = useDeleteFeed()
  const [deleteTarget, setDeleteTarget] = useState<FeedConfig | null>(null)

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="Feeds"
        description="Monitored pages that generate RSS feeds"
        actions={
          <Link
            to="/feeds/new"
            className="inline-flex items-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 bg-orange-500 hover:bg-orange-600 text-white px-2.5 py-1.5 text-sm"
          >
            <PlusCircle className="h-4 w-4" />
            New Feed
          </Link>
        }
      />

      <div className="p-6">
        {!feeds || feeds.length === 0 ? (
          <EmptyState
            title="No feeds yet"
            description="Create your first feed to start monitoring a web page and generating RSS."
            action={{ label: 'Create Feed', to: '/feeds/new' }}
          />
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Feed</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Last scraped</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Interval</th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {feeds.map((feed) => (
                  <FeedRow
                    key={feed.id}
                    feed={feed}
                    onDelete={() => setDeleteTarget(feed)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        title={`Delete "${deleteTarget?.title}"?`}
        description="This will permanently delete the feed and all its scraped items. This cannot be undone."
        confirmLabel="Delete"
        loading={deleteMutation.isPending}
        onConfirm={() => {
          if (deleteTarget) {
            deleteMutation.mutate(deleteTarget.id, {
              onSuccess: () => setDeleteTarget(null),
            })
          }
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  )
}

function FeedRow({ feed, onDelete }: { feed: FeedConfig; onDelete: () => void }) {
  const navigate = useNavigate()
  const scrape = useTriggerScrape(feed.id)

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-4 py-3">
        <div>
          <Link
            to={`/feeds/${feed.id}`}
            className="font-medium text-gray-800 hover:text-orange-600"
          >
            {feed.title}
          </Link>
          <div className="mt-0.5 flex items-center gap-1 text-xs text-gray-400">
            <span className="font-mono">{feed.slug}</span>
            <span>·</span>
            <a
              href={feed.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-0.5 hover:text-orange-500"
            >
              {new URL(feed.url).hostname}
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <FeedStatusBadge feed={feed} />
      </td>
      <td className="px-4 py-3 text-gray-500">{formatRelative(feed.last_scraped_at)}</td>
      <td className="px-4 py-3 text-gray-500">{feed.poll_interval_minutes}m</td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-1">
          <Button
            variant="ghost"
            size="sm"
            title="Scrape now"
            loading={scrape.isPending}
            onClick={() => scrape.mutate()}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            title="Edit"
            onClick={() => navigate(`/feeds/${feed.id}`)}
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" title="Delete" onClick={onDelete}>
            <Trash2 className="h-4 w-4 text-red-400" />
          </Button>
        </div>
      </td>
    </tr>
  )
}

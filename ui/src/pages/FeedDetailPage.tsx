import { useState } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { RefreshCw, Trash2 } from 'lucide-react'
import { PageHeader } from '../components/layout/PageHeader'
import { FeedStatusBadge } from '../components/feeds/FeedStatusBadge'
import { FeedForm } from '../components/feeds/FeedForm'
import { PreviewTable } from '../components/feeds/PreviewTable'
import { ScrapeLogList } from '../components/feeds/ScrapeLogList'
import { RssUrlCopy } from '../components/feeds/RssUrlCopy'
import { Toggle } from '../components/ui/Toggle'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { useFeed, useUpdateFeed, useDeleteFeed, useTriggerScrape } from '../hooks/useFeeds'
import { useFeedLogs } from '../hooks/useFeedLogs'
import { useQueryClient } from '@tanstack/react-query'
import { feedsApi } from '../api/feeds'
import type { FeedConfigCreate, RawItem } from '../api/types'
import { ApiError } from '../api/client'
import { formatDateTime } from '../lib/dates'

export function FeedDetailPage() {
  const { id } = useParams<{ id: string }>()
  const feedId = Number(id)
  const location = useLocation()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: feed, isLoading } = useFeed(feedId)
  const { data: logs } = useFeedLogs(feedId)
  const updateMutation = useUpdateFeed(feedId)
  const deleteMutation = useDeleteFeed()
  const scrapeMutation = useTriggerScrape(feedId)

  const [showDelete, setShowDelete] = useState(false)
  const [updateError, setUpdateError] = useState<string | undefined>()
  const [preview, setPreview] = useState<RawItem[] | null>(
    (location.state as { preview?: RawItem[] })?.preview ?? null,
  )
  const [isPreviewing, setIsPreviewing] = useState(false)

  if (isLoading || !feed) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    )
  }

  const handleUpdate = (data: FeedConfigCreate) => {
    setUpdateError(undefined)
    updateMutation.mutate(data, {
      onError: (err) => setUpdateError(err instanceof ApiError ? err.message : String(err)),
    })
  }

  const handlePreview = async () => {
    setIsPreviewing(true)
    try {
      const items = await feedsApi.preview(feedId)
      setPreview(items)
      qc.setQueryData(['preview', feedId], items)
    } catch (err) {
      setPreview([])
    } finally {
      setIsPreviewing(false)
    }
  }

  const handleDelete = () => {
    deleteMutation.mutate(feedId, {
      onSuccess: () => navigate('/'),
    })
  }

  return (
    <>
      <PageHeader
        title={feed.title}
        description={`/feed/${feed.slug}.xml`}
        actions={
          <div className="flex items-center gap-2">
            <FeedStatusBadge feed={feed} />
            <Button
              variant="outline"
              size="sm"
              loading={scrapeMutation.isPending}
              onClick={() => scrapeMutation.mutate()}
            >
              <RefreshCw className="h-4 w-4" />
              Scrape Now
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowDelete(true)}>
              <Trash2 className="h-4 w-4 text-red-400" />
            </Button>
          </div>
        }
      />

      <div className="mx-auto max-w-2xl space-y-8 p-6">
        {/* RSS URL + Active toggle */}
        <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700">RSS Feed URL</p>
              <p className="text-xs text-gray-400">Paste this into Feedly, Readwise, or Inoreader</p>
            </div>
            <Toggle
              label="Active"
              checked={feed.active}
              onChange={(v) => updateMutation.mutate({ active: v })}
            />
          </div>
          <RssUrlCopy slug={feed.slug} />
          {feed.last_scraped_at && (
            <p className="text-xs text-gray-400">Last scraped: {formatDateTime(feed.last_scraped_at)}</p>
          )}
        </div>

        {/* Edit form */}
        <div>
          <h2 className="mb-4 text-base font-semibold text-gray-800">Edit Configuration</h2>
          {updateMutation.isSuccess && (
            <p className="mb-3 text-sm text-green-600">Changes saved.</p>
          )}
          <FeedForm
            initialValues={{
              ...feed,
              selector_description: feed.selector_description ?? undefined,
              selector_date: feed.selector_date ?? undefined,
              selector_author: feed.selector_author ?? undefined,
              selector_item_excluded: feed.selector_item_excluded ?? undefined,
              date_format: feed.date_format ?? undefined,
              xpath_item: feed.xpath_item ?? undefined,
              xpath_title: feed.xpath_title ?? undefined,
              xpath_link: feed.xpath_link ?? undefined,
              xpath_description: feed.xpath_description ?? undefined,
              xpath_date: feed.xpath_date ?? undefined,
              xpath_author: feed.xpath_author ?? undefined,
            }}
            onSubmit={handleUpdate}
            isLoading={updateMutation.isPending}
            submitLabel="Save Changes"
            error={updateError}
            onPreview={handlePreview}
            isPreviewing={isPreviewing}
          />
        </div>

        {/* Selector preview */}
        {preview !== null && (
          <div>
            <h2 className="mb-3 text-base font-semibold text-gray-800">Selector Preview</h2>
            <PreviewTable items={preview} />
          </div>
        )}

        {/* Scrape logs */}
        <div>
          <h2 className="mb-3 text-base font-semibold text-gray-800">Scrape History</h2>
          <div className="rounded-lg border border-gray-200 bg-white px-4">
            <ScrapeLogList logs={logs ?? []} />
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={showDelete}
        title={`Delete "${feed.title}"?`}
        description="This will permanently delete the feed and all its scraped items. This cannot be undone."
        confirmLabel="Delete"
        loading={deleteMutation.isPending}
        onConfirm={handleDelete}
        onCancel={() => setShowDelete(false)}
      />
    </>
  )
}

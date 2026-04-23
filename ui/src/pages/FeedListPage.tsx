import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PlusCircle, RefreshCw, Trash2, Pencil, ExternalLink, Download, Tag, ChevronDown, ChevronRight } from 'lucide-react'
import { PageHeader } from '../components/layout/PageHeader'
import { FeedStatusBadge } from '../components/feeds/FeedStatusBadge'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/ui/EmptyState'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { useFeedList, useDeleteFeed, useTriggerScrape, useUpdateFeed } from '../hooks/useFeeds'
import { formatRelative } from '../lib/dates'
import type { FeedConfig } from '../api/types'

export function FeedListPage() {
  const { data: feeds, isLoading } = useFeedList()
  const deleteMutation = useDeleteFeed()
  const [deleteTarget, setDeleteTarget] = useState<FeedConfig | null>(null)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const toggleGroup = (key: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Group feeds: labeled groups (sorted A-Z) first, then unlabeled
  const feedGroups: { label: string | null; feeds: FeedConfig[] }[] = (() => {
    if (!feeds || feeds.length === 0) return []
    const groups = new Map<string, FeedConfig[]>()
    const unlabeled: FeedConfig[] = []
    for (const feed of feeds) {
      if (feed.label) {
        if (!groups.has(feed.label)) groups.set(feed.label, [])
        groups.get(feed.label)!.push(feed)
      } else {
        unlabeled.push(feed)
      }
    }
    const sorted = Array.from(groups.keys()).sort((a, b) => a.localeCompare(b))
    return [
      ...sorted.map(l => ({ label: l, feeds: groups.get(l)! })),
      ...(unlabeled.length > 0 ? [{ label: null, feeds: unlabeled }] : []),
    ]
  })()

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
          <div className="flex items-center gap-2">
            {feeds && feeds.length > 0 && (
              <a
                href="/api/feeds/opml"
                download="feeds.opml"
                className="inline-flex items-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 px-2.5 py-1.5 text-sm"
              >
                <Download className="h-4 w-4" />
                Export OPML
              </a>
            )}
            <Link
              to="/feeds/new"
              className="inline-flex items-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 bg-orange-500 hover:bg-orange-600 text-white px-2.5 py-1.5 text-sm"
            >
              <PlusCircle className="h-4 w-4" />
              New Feed
            </Link>
          </div>
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
          <div className="space-y-6">
            {feedGroups.map(({ label, feeds: groupFeeds }) => {
              const key = label ?? '__unlabeled'
              const isCollapsed = collapsed.has(key)
              return (
                <div key={key}>
                  <button
                    onClick={() => toggleGroup(key)}
                    className="mb-2 flex items-center gap-1 text-sm font-semibold uppercase tracking-wide text-gray-500 hover:text-gray-700 transition-colors"
                  >
                    {isCollapsed
                      ? <ChevronRight className="h-3.5 w-3.5" />
                      : <ChevronDown className="h-3.5 w-3.5" />
                    }
                    {label ?? 'Unlabeled'}
                    <span className="ml-1 text-xs font-normal normal-case text-gray-400">({groupFeeds.length})</span>
                  </button>
                  {!isCollapsed && (
                    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
                      <table className="w-full text-sm">
                        <thead className="border-b border-gray-200 bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Feed</th>
                            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Label</th>
                            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Status</th>
                            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Last scraped</th>
                            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Interval</th>
                            <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Items</th>
                            <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {groupFeeds.map((feed) => (
                            <FeedRow
                              key={feed.id}
                              feed={feed}
                              allLabels={feedGroups.flatMap(g => g.label ? [g.label] : [])}
                              onDelete={() => setDeleteTarget(feed)}
                            />
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )
            })}
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

function FeedRow({ feed, allLabels, onDelete }: { feed: FeedConfig; allLabels: string[]; onDelete: () => void }) {
  const navigate = useNavigate()
  const scrape = useTriggerScrape(feed.id)
  const update = useUpdateFeed(feed.id)
  const [editingLabel, setEditingLabel] = useState(false)
  const [labelValue, setLabelValue] = useState(feed.label ?? '')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setLabelValue(feed.label ?? '') }, [feed.label])
  useEffect(() => { if (editingLabel) inputRef.current?.focus() }, [editingLabel])

  const saveLabel = () => {
    setEditingLabel(false)
    const next = labelValue.trim() || null
    if (next !== (feed.label ?? null)) {
      update.mutate({ label: next })
    }
  }

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-4 py-3">
        <div>
          <Link to={`/feeds/${feed.id}`} className="font-medium text-gray-800 hover:text-orange-600">
            {feed.title}
          </Link>
          <div className="mt-0.5 flex items-center gap-1 text-xs text-gray-400">
            <span className="font-mono">{feed.slug}</span>
            <span>·</span>
            <a href={feed.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-0.5 hover:text-orange-500">
              {new URL(feed.url).hostname}
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </td>

      {/* Inline label cell */}
      <td className="px-4 py-3">
        {editingLabel ? (
          <div className="relative">
            <input
              ref={inputRef}
              value={labelValue}
              onChange={e => setLabelValue(e.target.value)}
              onBlur={saveLabel}
              onKeyDown={e => { if (e.key === 'Enter') saveLabel(); if (e.key === 'Escape') { setLabelValue(feed.label ?? ''); setEditingLabel(false) } }}
              list={`labels-${feed.id}`}
              placeholder="Add label…"
              className="w-32 rounded border border-orange-400 px-2 py-0.5 text-xs outline-none focus:ring-1 focus:ring-orange-400"
            />
            <datalist id={`labels-${feed.id}`}>
              {allLabels.map(l => <option key={l} value={l} />)}
            </datalist>
          </div>
        ) : feed.label ? (
          <button
            onClick={() => setEditingLabel(true)}
            title="Click to change label"
            className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-medium text-orange-700 hover:bg-orange-200 transition-colors"
          >
            <Tag className="h-3 w-3" />
            {feed.label}
          </button>
        ) : (
          <button
            onClick={() => setEditingLabel(true)}
            title="Add label"
            className="text-xs text-gray-300 hover:text-gray-500 transition-colors"
          >
            + label
          </button>
        )}
      </td>

      <td className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <FeedStatusBadge feed={feed} />
          {feed.active && feed.last_scraped_at && feed.item_count === 0 && (
            <span
              title="No items found — check your selectors or enable Playwright"
              className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"
            >
              ⚠ Empty
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-gray-500">{formatRelative(feed.last_scraped_at)}</td>
      <td className="px-4 py-3 text-gray-500">{feed.poll_interval_minutes}m</td>
      <td className="px-4 py-3 text-right tabular-nums">
        <a
          href={`/feed/${feed.slug}.xml`}
          target="_blank"
          rel="noopener noreferrer"
          title="Open RSS feed"
          className="tabular-nums text-orange-500 hover:text-orange-700 hover:underline"
        >
          {feed.item_count}
        </a>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-1">
          <Button variant="ghost" size="sm" title="Scrape now" loading={scrape.isPending} onClick={() => scrape.mutate()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" title="Edit" onClick={() => navigate(`/feeds/${feed.id}`)}>
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

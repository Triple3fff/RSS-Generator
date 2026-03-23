import { useEffect, useRef, useState } from 'react'
import { XCircle } from 'lucide-react'

export interface PickerSelectors {
  selector_item?: string
  selector_title?: string
  selector_link?: string
  selector_description?: string
  selector_date?: string
  selector_author?: string
  selector_item_excluded?: string
}

interface VisualPickerProps {
  url: string
  initialSelectors?: PickerSelectors
  usePlaywright?: boolean
  onComplete: (result: PickerSelectors) => void
  onClose: (partial: PickerSelectors) => void
  onTogglePlaywright?: () => void
}

const FIELD_LABELS: { key: keyof PickerSelectors; label: string; auto?: boolean }[] = [
  { key: 'selector_item',        label: 'Container' },
  { key: 'selector_title',       label: 'Title' },
  { key: 'selector_link',        label: 'Link',        auto: true },
  { key: 'selector_description', label: 'Description' },
  { key: 'selector_date',        label: 'Date' },
  { key: 'selector_author',      label: 'Author' },
]

function buildSrc(url: string, initialSelectors?: PickerSelectors, usePlaywright?: boolean): string {
  let base = `/api/picker?url=${encodeURIComponent(url)}`
  if (usePlaywright) base += '&use_playwright=true'
  if (!initialSelectors) return base
  const filled = Object.fromEntries(
    Object.entries(initialSelectors).filter(([, v]) => Boolean(v)),
  )
  if (Object.keys(filled).length === 0) return base
  return base + `&sel=${encodeURIComponent(JSON.stringify(filled))}`
}

export function VisualPicker({ url, initialSelectors, usePlaywright, onComplete, onClose, onTogglePlaywright }: VisualPickerProps) {
  const [selectors, setSelectors] = useState<PickerSelectors>(initialSelectors ?? {})
  const [needsPlaywright, setNeedsPlaywright] = useState(false)
  const selectorsRef = useRef<PickerSelectors>(initialSelectors ?? {})
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    selectorsRef.current = selectors
  }, [selectors])

  useEffect(() => {
    function handler(e: MessageEvent) {
      if (e.data?.type === 'rss-picker-needs-playwright') {
        setNeedsPlaywright(true)
      } else if (e.data?.type === 'rss-picker-field') {
        const updated = { ...selectorsRef.current }
        if (e.data.selector === '') {
          delete updated[e.data.field as keyof PickerSelectors]
        } else {
          updated[e.data.field as keyof PickerSelectors] = e.data.selector
        }
        selectorsRef.current = updated
        setSelectors(updated)
      } else if (e.data?.type === 'rss-picker-done') {
        onComplete(e.data.selectors ?? selectorsRef.current)
      } else if (e.data?.type === 'rss-picker-cancel') {
        onClose(selectorsRef.current)
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [onComplete, onClose])

  // Selectors are passed via ?sel= param baked into the iframe src — no postMessage needed
  const src = buildSrc(url, initialSelectors, usePlaywright)

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/80">
      {/* Status bar */}
      <div className="flex shrink-0 items-center gap-3 bg-gray-900 px-4 py-2">
        <span className="font-bold text-orange-400">Visual Selector Picker</span>
        <div className="flex flex-1 flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {FIELD_LABELS.map(({ key, label, auto }) => {
            const value = selectors[key]
            if (!value) return null
            return (
              <span key={key} className={auto ? 'text-blue-400' : 'text-green-400'}>
                {auto ? '⚙' : '✓'} {label}
              </span>
            )
          })}
          {!selectors.selector_title && (
            <span className="text-gray-500">Click an article element to start</span>
          )}
        </div>
        <button
          onClick={() => iframeRef.current?.contentWindow?.postMessage({ type: 'rss-picker-dismiss-popup' }, '*')}
          title="Dismiss cookie consent popup"
          className="shrink-0 flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors bg-gray-700 text-gray-400 hover:bg-gray-600 hover:text-gray-200"
        >
          <XCircle className="h-3.5 w-3.5" />
          Dismiss Popup
        </button>
        {onTogglePlaywright && (
          <button
            onClick={onTogglePlaywright}
            title="Toggle Playwright (headless browser) for JavaScript-rendered pages"
            className={`shrink-0 flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
              usePlaywright
                ? 'bg-green-800 text-green-300 hover:bg-green-700'
                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${usePlaywright ? 'bg-green-400' : 'bg-gray-500'}`} />
            Playwright
          </button>
        )}
      </div>

      {/* Instructions */}
      <div className="shrink-0 bg-gray-800 px-4 py-1.5 text-xs text-gray-400">
        Hover to highlight · Click → assign as <span className="text-orange-300">Container</span>,{' '}
        <span className="text-orange-300">Title</span>,{' '}
        <span className="text-orange-300">Description</span>,{' '}
        <span className="text-orange-300">Date</span>, or{' '}
        <span className="text-orange-300">Author</span>.
        Use <kbd className="rounded bg-gray-700 px-1">↑ Parent</kbd> /{' '}
        <kbd className="rounded bg-gray-700 px-1">↓ Child</kbd> to navigate.
        {initialSelectors?.selector_item && (
          <span className="ml-3 text-green-400">
            ◉ Click <strong>Previous Selections</strong> in the page toolbar to restore highlights
          </span>
        )}
      </div>

      {/* Playwright warning — shown when the page appears to be JS-rendered */}
      {needsPlaywright && !usePlaywright && (
        <div className="shrink-0 flex items-center gap-3 bg-amber-900/80 border-b border-amber-600 px-4 py-2 text-sm text-amber-200">
          <span className="text-amber-400 text-base">⚠</span>
          <span className="flex-1">
            This page appears to be JavaScript-rendered. The content shown may be empty or incomplete.
            Enable <strong>Use Playwright</strong> to load the full page.
          </span>
          {onTogglePlaywright && (
            <button
              onClick={onTogglePlaywright}
              className="shrink-0 rounded bg-amber-500 px-3 py-1 text-xs font-semibold text-white hover:bg-amber-400"
            >
              Enable Playwright
            </button>
          )}
        </div>
      )}

      {/* Proxied page — selectors are baked into the URL so no postMessage handshake needed */}
      <iframe
        ref={iframeRef}
        src={src}
        className="flex-1 border-0 bg-white"
        sandbox="allow-scripts"
        title="Visual selector picker"
      />
    </div>
  )
}

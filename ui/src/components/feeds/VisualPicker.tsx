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
  waitSeconds?: number
  onComplete: (result: PickerSelectors) => void
  onClose: (partial: PickerSelectors) => void
  onTogglePlaywright?: () => void
  onChangeWaitSeconds?: (seconds: number) => void
}

const FIELD_LABELS: { key: keyof PickerSelectors; label: string; auto?: boolean }[] = [
  { key: 'selector_item',        label: 'Container' },
  { key: 'selector_title',       label: 'Title' },
  { key: 'selector_link',        label: 'Link',        auto: true },
  { key: 'selector_description', label: 'Description' },
  { key: 'selector_date',        label: 'Date' },
  { key: 'selector_author',      label: 'Author' },
]

function buildSrc(
  url: string,
  initialSelectors?: PickerSelectors,
  usePlaywright?: boolean,
  waitSeconds?: number,
): string {
  let base = `/api/picker?url=${encodeURIComponent(url)}`
  if (usePlaywright) base += '&use_playwright=true'
  if (usePlaywright && waitSeconds && waitSeconds > 0) base += `&wait_seconds=${waitSeconds}`
  if (!initialSelectors) return base
  const filled = Object.fromEntries(
    Object.entries(initialSelectors).filter(([, v]) => Boolean(v)),
  )
  if (Object.keys(filled).length === 0) return base
  return base + `&sel=${encodeURIComponent(JSON.stringify(filled))}`
}

export function VisualPicker({
  url,
  initialSelectors,
  usePlaywright,
  waitSeconds = 0,
  onComplete,
  onClose,
  onTogglePlaywright,
  onChangeWaitSeconds,
}: VisualPickerProps) {
  const [selectors, setSelectors] = useState<PickerSelectors>(initialSelectors ?? {})
  const [needsPlaywright, setNeedsPlaywright] = useState(false)
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const selectorsRef = useRef<PickerSelectors>(initialSelectors ?? {})
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    selectorsRef.current = selectors
  }, [selectors])

  useEffect(() => {
    function handler(e: MessageEvent) {
      if (e.data?.type === 'rss-picker-needs-playwright') {
        setNeedsPlaywright(true)
      } else if (e.data?.type === 'rss-picker-auto-playwright') {
        // Server silently upgraded Static→Playwright (CSR bailout detected).
        // Flip the toggle so the saved feed config also uses Playwright.
        if (!usePlaywright && onTogglePlaywright) onTogglePlaywright()
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

  function handleLoad() {
    setIsLoading(true)
    setNeedsPlaywright(false)
    setLoadedSrc(buildSrc(url, initialSelectors, usePlaywright, waitSeconds))
    setReloadKey(k => k + 1)
  }

  const isLoaded = loadedSrc !== null

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/80">

      {/* ── Top toolbar ── */}
      <div className="flex shrink-0 items-center gap-3 bg-gray-900 px-4 py-2">
        <span className="font-bold text-orange-400 shrink-0">Visual Selector Picker</span>

        {/* Field completion status — only after loading */}
        {isLoaded ? (
          <div className="flex flex-1 flex-wrap items-center gap-x-3 gap-y-1 text-xs min-w-0">
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
        ) : (
          <div className="flex-1" />
        )}

        {/* Dismiss popup — only after loading */}
        {isLoaded && (
          <button
            onClick={() => iframeRef.current?.contentWindow?.postMessage({ type: 'rss-picker-dismiss-popup' }, '*')}
            title="Dismiss cookie consent popup"
            className="shrink-0 flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors bg-gray-700 text-gray-400 hover:bg-gray-600 hover:text-gray-200"
          >
            <XCircle className="h-3.5 w-3.5" />
            Dismiss Popup
          </button>
        )}

        {/* ── Source mode: Static / Dynamic ── */}
        {onTogglePlaywright && (
          <div className="shrink-0 flex items-center gap-2">
            <span className="text-xs text-gray-500">Source:</span>
            <div className="flex rounded overflow-hidden border border-gray-600 text-xs font-medium">
              <button
                type="button"
                onClick={() => usePlaywright && onTogglePlaywright()}
                className={`px-3 py-1 transition-colors ${
                  !usePlaywright
                    ? 'bg-gray-500 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
                }`}
                title="Fetch page with a plain HTTP request — fast, works for server-rendered sites"
              >
                Static
              </button>
              <button
                type="button"
                onClick={() => !usePlaywright && onTogglePlaywright()}
                className={`px-3 py-1 transition-colors ${
                  usePlaywright
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
                }`}
                title="Use a headless browser to execute JavaScript — required for dynamically-rendered pages"
              >
                Dynamic
              </button>
            </div>

            {/* Wait time — only in Dynamic mode */}
            {usePlaywright && (
              <div className="flex items-center gap-1.5" title="Extra seconds to wait for dynamic content to finish loading">
                <span className="text-gray-400 text-xs">⏱</span>
                <input
                  type="number"
                  min={0}
                  max={120}
                  value={waitSeconds}
                  onChange={(e) => onChangeWaitSeconds?.(Math.max(0, Math.min(120, Number(e.target.value))))}
                  className="w-14 bg-gray-800 border border-gray-600 rounded px-2 py-0.5 text-xs text-gray-200 text-center focus:outline-none focus:border-orange-500"
                />
                <span className="text-gray-400 text-xs">s wait</span>
              </div>
            )}
          </div>
        )}

        {/* ── Load / Reload button ── */}
        <button
          type="button"
          onClick={handleLoad}
          disabled={isLoading}
          className={`shrink-0 flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition-colors ${
            isLoading
              ? 'bg-gray-700 text-gray-500 cursor-wait'
              : isLoaded
                ? 'bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white'
                : 'bg-orange-600 text-white hover:bg-orange-500'
          }`}
          title={isLoaded ? 'Reload the page with the current source settings' : 'Fetch the page and open the visual selector'}
        >
          {isLoading ? '⏳ Loading…' : isLoaded ? '↺ Reload' : '▶ Load Page'}
        </button>
      </div>

      {/* ── Instructions bar — only when loaded ── */}
      {isLoaded && (
        <div className="shrink-0 bg-gray-800 px-4 py-1.5 text-xs text-gray-400">
          Hover to highlight · Click → assign as{' '}
          <span className="text-orange-300">Container</span>,{' '}
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
      )}

      {/* ── JS-rendered page warning — only when loaded ── */}
      {isLoaded && needsPlaywright && !usePlaywright && (
        <div className="shrink-0 flex items-center gap-3 bg-amber-900/80 border-b border-amber-600 px-4 py-2 text-sm text-amber-200">
          <span className="text-amber-400 text-base">⚠</span>
          <span className="flex-1">
            This page appears to be JavaScript-rendered. The content shown may be empty or incomplete.
            Switch to <strong>Dynamic</strong> and reload the page.
          </span>
          {onTogglePlaywright && (
            <button
              onClick={() => { if (!usePlaywright) { onTogglePlaywright(); } }}
              className="shrink-0 rounded bg-amber-500 px-3 py-1 text-xs font-semibold text-white hover:bg-amber-400"
            >
              Switch to Dynamic
            </button>
          )}
        </div>
      )}

      {/* ── Main content area ── */}
      {!isLoaded ? (

        /* Pre-load: configuration panel */
        <div className="flex-1 flex items-center justify-center bg-gray-950">
          <div className="text-center space-y-6 p-10 rounded-2xl bg-gray-800/60 border border-gray-700 max-w-lg w-full mx-8">
            <div className="text-4xl">🌐</div>
            <div className="space-y-1">
              <p className="text-gray-200 font-medium text-sm break-all">{url}</p>
              <p className="text-gray-500 text-sm">
                {usePlaywright
                  ? `Dynamic mode — headless browser executes JavaScript${waitSeconds > 0 ? ` · ${waitSeconds}s extra wait` : ''}`
                  : 'Static mode — plain HTTP request'}
              </p>
            </div>
            <button
              type="button"
              onClick={handleLoad}
              className="inline-flex items-center gap-2 rounded-lg bg-orange-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-orange-500 transition-colors"
            >
              ▶ Load Page
            </button>
            <p className="text-gray-600 text-xs">
              Configure source mode above, then click Load Page
            </p>
          </div>
        </div>

      ) : (

        /* Loaded: iframe with optional loading overlay */
        <div className="relative flex-1">
          <iframe
            key={reloadKey}
            ref={iframeRef}
            src={loadedSrc}
            onLoad={() => setIsLoading(false)}
            className="w-full h-full border-0 bg-white"
            sandbox="allow-scripts"
            title="Visual selector picker"
          />
          {isLoading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-950/85">
              <div className="text-center space-y-4">
                <div className="text-4xl animate-pulse">⏳</div>
                <p className="text-gray-200 font-medium text-sm">
                  {usePlaywright ? 'Launching headless browser…' : 'Fetching page…'}
                </p>
                {usePlaywright && waitSeconds > 0 && (
                  <p className="text-gray-400 text-xs">Waiting {waitSeconds}s for dynamic content to load</p>
                )}
              </div>
            </div>
          )}
        </div>

      )}
    </div>
  )
}

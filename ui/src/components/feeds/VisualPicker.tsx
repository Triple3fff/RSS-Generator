import { useEffect, useRef, useState } from 'react'

export interface PickerSelectors {
  selector_item?: string
  selector_title?: string
  selector_link?: string
  selector_description?: string
  selector_date?: string
  selector_author?: string
}

interface VisualPickerProps {
  url: string
  initialSelectors?: PickerSelectors
  onComplete: (result: PickerSelectors) => void
  onClose: () => void
}

const FIELD_LABELS: { key: keyof PickerSelectors; label: string; auto?: boolean }[] = [
  { key: 'selector_item',        label: 'Container' },
  { key: 'selector_title',       label: 'Title' },
  { key: 'selector_link',        label: 'Link',         auto: true },
  { key: 'selector_description', label: 'Description' },
  { key: 'selector_date',        label: 'Date' },
  { key: 'selector_author',      label: 'Author' },
]

export function VisualPicker({ url, initialSelectors, onComplete, onClose }: VisualPickerProps) {
  const [selectors, setSelectors] = useState<PickerSelectors>(initialSelectors ?? {})
  const selectorsRef = useRef<PickerSelectors>(initialSelectors ?? {})
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    selectorsRef.current = selectors
  }, [selectors])

  const handleIframeLoad = () => {
    const init = selectorsRef.current
    if (Object.values(init).some(Boolean) && iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.postMessage(
        { type: 'rss-picker-init', selectors: init },
        '*',
      )
    }
  }

  useEffect(() => {
    function handler(e: MessageEvent) {
      if (e.data?.type === 'rss-picker-field') {
        // A field was selected — picker also sends selector_item/selector_link
        // via the 'rss-picker-done' message; individual updates just refresh display
        const updated = { ...selectorsRef.current, [e.data.field]: e.data.selector }
        selectorsRef.current = updated
        setSelectors(updated)
      } else if (e.data?.type === 'rss-picker-done') {
        // Full selectors object including auto-detected fields
        onComplete(e.data.selectors ?? selectorsRef.current)
      } else if (e.data?.type === 'rss-picker-cancel') {
        onClose()
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [onComplete, onClose])

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/80">
      {/* Header */}
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
            <span className="text-gray-500">Click an article title to start</span>
          )}
        </div>

        <button
          onClick={() => onComplete(selectorsRef.current)}
          className="rounded-md bg-orange-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-orange-600"
        >
          Apply Selectors
        </button>
        <button
          onClick={onClose}
          className="rounded-md bg-gray-700 px-3 py-1.5 text-sm text-white hover:bg-gray-600"
        >
          Cancel
        </button>
      </div>

      {/* Instructions */}
      <div className="shrink-0 bg-gray-800 px-4 py-1.5 text-xs text-gray-400">
        Hover to highlight · Click → assign as <span className="text-orange-300">Title</span>{' '}
        (auto-detects container &amp; link), <span className="text-orange-300">Description</span>,{' '}
        <span className="text-orange-300">Date</span>, or <span className="text-orange-300">Author</span>.
        Use <kbd className="rounded bg-gray-700 px-1">↑ Parent</kbd> /{' '}
        <kbd className="rounded bg-gray-700 px-1">↓ Child</kbd> to navigate the element tree.
      </div>

      {/* Proxied page */}
      <iframe
        ref={iframeRef}
        src={`/api/picker?url=${encodeURIComponent(url)}`}
        className="flex-1 border-0 bg-white"
        sandbox="allow-scripts"
        title="Visual selector picker"
        onLoad={handleIframeLoad}
      />
    </div>
  )
}

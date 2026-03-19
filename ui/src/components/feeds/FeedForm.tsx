import { useState } from 'react'
import { Input } from '../ui/Input'
import { Toggle } from '../ui/Toggle'
import { Button } from '../ui/Button'
import { Tooltip } from '../ui/Tooltip'
import { ErrorBanner } from '../ui/ErrorBanner'
import { VisualPicker } from './VisualPicker'
import type { FeedConfigCreate } from '../../api/types'

interface FeedFormProps {
  initialValues?: Partial<FeedConfigCreate>
  onSubmit: (data: FeedConfigCreate) => void
  isLoading?: boolean
  submitLabel?: string
  error?: string
  /** Called when "Test Selectors" is clicked — only available in edit mode */
  onPreview?: () => void
  isPreviewing?: boolean
}

function slugify(s: string) {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

export function FeedForm({
  initialValues,
  onSubmit,
  isLoading,
  submitLabel = 'Create Feed',
  error,
  onPreview,
  isPreviewing,
}: FeedFormProps) {
  const [form, setForm] = useState<FeedConfigCreate>({
    slug: initialValues?.slug ?? '',
    url: initialValues?.url ?? '',
    title: initialValues?.title ?? '',
    description: initialValues?.description ?? '',
    selector_item: initialValues?.selector_item ?? '',
    selector_title: initialValues?.selector_title ?? '',
    selector_link: initialValues?.selector_link ?? '',
    selector_link_attr: initialValues?.selector_link_attr ?? 'href',
    selector_description: initialValues?.selector_description ?? '',
    selector_date: initialValues?.selector_date ?? '',
    selector_author: initialValues?.selector_author ?? '',
    date_format: initialValues?.date_format ?? '',
    poll_interval_minutes: initialValues?.poll_interval_minutes ?? 60,
    use_playwright: initialValues?.use_playwright ?? false,
    keep_html: initialValues?.keep_html ?? false,
  })

  const [slugManuallyEdited, setSlugManuallyEdited] = useState(!!initialValues?.slug)
  const [showAdvanced, setShowAdvanced] = useState(
    !!(initialValues?.selector_description || initialValues?.selector_date || initialValues?.selector_author),
  )
  const [showPicker, setShowPicker] = useState(false)

  const set = <K extends keyof FeedConfigCreate>(key: K, value: FeedConfigCreate[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const handleTitleChange = (title: string) => {
    set('title', title)
    if (!slugManuallyEdited) set('slug', slugify(title))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const cleaned: FeedConfigCreate = {
      ...form,
      selector_description: form.selector_description || undefined,
      selector_date: form.selector_date || undefined,
      selector_author: form.selector_author || undefined,
      date_format: form.date_format || undefined,
    }
    onSubmit(cleaned)
  }

  const handlePickerComplete = (result: import('./VisualPicker').PickerSelectors) => {
    setShowPicker(false)
    if (result.selector_item)  set('selector_item',  result.selector_item)
    if (result.selector_title) set('selector_title', result.selector_title)
    if (result.selector_link)  set('selector_link',  result.selector_link)
    if (result.selector_description || result.selector_date || result.selector_author) {
      setShowAdvanced(true)
      if (result.selector_description) set('selector_description', result.selector_description)
      if (result.selector_date)        set('selector_date',        result.selector_date)
      if (result.selector_author)      set('selector_author',      result.selector_author)
    }
  }

  return (
    <>
    {showPicker && (
      <VisualPicker
        url={form.url}
        initialSelectors={{
          selector_item:        form.selector_item        || undefined,
          selector_title:       form.selector_title       || undefined,
          selector_link:        form.selector_link        || undefined,
          selector_description: form.selector_description || undefined,
          selector_date:        form.selector_date        || undefined,
          selector_author:      form.selector_author      || undefined,
        }}
        onComplete={handlePickerComplete}
        onClose={() => setShowPicker(false)}
      />
    )}
    <form onSubmit={handleSubmit} className="space-y-8">
      {error && <ErrorBanner message={error} />}

      {/* Basic info */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Basic Info</h3>
        <Input
          label="Title"
          required
          value={form.title}
          onChange={(e) => handleTitleChange(e.target.value)}
          placeholder="My Blog Feed"
        />
        <Input
          label="Slug"
          required
          mono
          value={form.slug}
          onChange={(e) => {
            setSlugManuallyEdited(true)
            set('slug', e.target.value)
          }}
          hint="Used in the feed URL: /feed/{slug}.xml"
          placeholder="my-blog-feed"
        />
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <Input
              label="Source URL"
              required
              type="url"
              value={form.url}
              onChange={(e) => set('url', e.target.value)}
              placeholder="https://example.com/blog"
            />
          </div>
          {form.url && (
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => setShowPicker(true)}
              title="Open the page and click to pick CSS selectors visually"
            >
              Visual Picker
            </Button>
          )}
        </div>
        <Input
          label="Description"
          value={form.description ?? ''}
          onChange={(e) => set('description', e.target.value)}
          placeholder="A short description of this feed"
        />
      </section>

      {/* CSS Selectors */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          CSS Selectors
        </h3>

        <div className="flex items-end gap-2">
          <div className="flex-1">
            <Input
              label="Item container"
              required
              mono
              value={form.selector_item}
              onChange={(e) => set('selector_item', e.target.value)}
              placeholder="article.post"
            />
          </div>
          <Tooltip content="CSS selector for the repeating container of each item. e.g. 'article.post', 'ul.feed > li'" />
        </div>

        <div className="flex items-end gap-2">
          <div className="flex-1">
            <Input
              label="Title"
              required
              mono
              value={form.selector_title}
              onChange={(e) => set('selector_title', e.target.value)}
              placeholder="h2 a"
            />
          </div>
          <Tooltip content="CSS selector for the title, relative to the item container. e.g. 'h2', '.post-title a'" />
        </div>

        {/* Advanced / optional selectors */}
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs font-medium text-orange-600 hover:underline"
        >
          {showAdvanced ? '▾ Hide optional selectors' : '▸ Show optional selectors'}
        </button>

        {showAdvanced && (
          <div className="space-y-4 rounded-md border border-gray-200 p-4">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Input
                  label="Description"
                  mono
                  value={form.selector_description ?? ''}
                  onChange={(e) => set('selector_description', e.target.value)}
                  placeholder="p.summary"
                />
              </div>
              <Tooltip content="Optional. CSS selector for the item description/summary text." />
            </div>

            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Input
                  label="Author"
                  mono
                  value={form.selector_author ?? ''}
                  onChange={(e) => set('selector_author', e.target.value)}
                  placeholder=".author-name"
                />
              </div>
              <Tooltip content="Optional. CSS selector for the author name." />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <Input
                    label="Date"
                    mono
                    value={form.selector_date ?? ''}
                    onChange={(e) => set('selector_date', e.target.value)}
                    placeholder="time"
                  />
                </div>
                <Tooltip content="Optional. CSS selector for the publication date element. Works with <time datetime='...'> automatically." />
              </div>
              <Input
                label="Date format"
                mono
                value={form.date_format ?? ''}
                onChange={(e) => set('date_format', e.target.value)}
                placeholder="%Y-%m-%d"
                hint="strptime format. Leave blank for auto-detect."
              />
            </div>

            <div className="grid grid-cols-3 gap-3 border-t border-gray-100 pt-4">
              <div className="col-span-2 flex items-end gap-2">
                <div className="flex-1">
                  <Input
                    label="Link (auto-detected if empty)"
                    mono
                    value={form.selector_link ?? ''}
                    onChange={(e) => set('selector_link', e.target.value)}
                    placeholder="a.read-more"
                    hint="Leave blank to use the first <a href> in each article."
                  />
                </div>
                <Tooltip content="Override the auto-detected link selector. Relative to item container." />
              </div>
              <Input
                label="Link attribute"
                mono
                value={form.selector_link_attr}
                onChange={(e) => set('selector_link_attr', e.target.value)}
                placeholder="href"
              />
            </div>
          </div>
        )}
      </section>

      {/* Options */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Options</h3>
        <Input
          label="Poll interval (minutes)"
          type="number"
          min={5}
          value={form.poll_interval_minutes}
          onChange={(e) => set('poll_interval_minutes', Number(e.target.value))}
        />
        <Toggle
          label="Use Playwright"
          description="Enable for JavaScript-rendered pages. Requires Playwright installed."
          checked={form.use_playwright ?? false}
          onChange={(v) => set('use_playwright', v)}
        />
        <Toggle
          label="Keep HTML in description"
          description="Preserve HTML tags in description. Some feed readers render them."
          checked={form.keep_html ?? false}
          onChange={(v) => set('keep_html', v)}
        />
      </section>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={isLoading}>
          {submitLabel}
        </Button>
        {onPreview && (
          <Button type="button" variant="outline" onClick={onPreview} loading={isPreviewing}>
            Test Selectors
          </Button>
        )}
      </div>
    </form>
    </>
  )
}

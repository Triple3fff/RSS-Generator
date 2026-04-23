import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/layout/PageHeader'
import { FeedForm } from '../components/feeds/FeedForm'
import { PreviewTable } from '../components/feeds/PreviewTable'
import { useCreateFeed } from '../hooks/useFeeds'
import type { FeedConfigCreate, RawItem } from '../api/types'
import { useState } from 'react'
import { ApiError } from '../api/client'

const FORM_ID = 'new-feed-form'

export function FeedNewPage() {
  const navigate = useNavigate()
  const createMutation = useCreateFeed()
  const [preview, setPreview] = useState<RawItem[] | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | undefined>()

  const handleSubmit = (data: FeedConfigCreate) => {
    setErrorMsg(undefined)
    createMutation.mutate(data, {
      onSuccess: (res) => {
        setPreview(res.preview)
        // Short delay so user sees the preview flash, then navigate
        setTimeout(() => navigate(`/feeds/${res.feed.id}`, { state: { preview: res.preview } }), 800)
      },
      onError: (err) => {
        setErrorMsg(err instanceof ApiError ? err.message : String(err))
      },
    })
  }

  return (
    <>
      <PageHeader
        title="New Feed"
        description="Define a page to monitor and the CSS selectors for extracting items."
        actions={
          <button
            type="submit"
            form={FORM_ID}
            disabled={createMutation.isPending}
            className="inline-flex items-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white px-2.5 py-1.5 text-sm"
          >
            {createMutation.isPending ? 'Creating…' : 'Create Feed'}
          </button>
        }
      />

      <div className="mx-auto max-w-2xl p-6">
        <FeedForm
          formId={FORM_ID}
          onSubmit={handleSubmit}
          isLoading={createMutation.isPending}
          submitLabel="Create Feed"
          error={errorMsg}
        />

        {preview && (
          <div className="mt-8">
            <h3 className="mb-3 text-sm font-semibold text-gray-700">Preview (first 3 items)</h3>
            <PreviewTable items={preview} />
          </div>
        )}
      </div>
    </>
  )
}

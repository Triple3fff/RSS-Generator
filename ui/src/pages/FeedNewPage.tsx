import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/layout/PageHeader'
import { FeedForm } from '../components/feeds/FeedForm'
import { PreviewTable } from '../components/feeds/PreviewTable'
import { useCreateFeed } from '../hooks/useFeeds'
import type { FeedConfigCreate, RawItem } from '../api/types'
import { useState } from 'react'
import { ApiError } from '../api/client'

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
      />

      <div className="mx-auto max-w-2xl p-6">
        <FeedForm
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

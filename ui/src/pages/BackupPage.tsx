import { useRef, useState } from 'react'
import { Download, Upload, AlertTriangle, CheckCircle } from 'lucide-react'
import { PageHeader } from '../components/layout/PageHeader'
import { Button } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { getToken } from '../api/client'

export function BackupPage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const [fileData, setFileData] = useState<object | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)

  // ── Export ──────────────────────────────────────────────────────────────────
  const handleExport = async () => {
    const res = await fetch('/api/backup', {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) { alert('Export failed'); return }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const date = new Date().toISOString().slice(0, 10)
    a.download = `rss_backup_${date}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── File selection ──────────────────────────────────────────────────────────
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setResult(null)
    setFileError(null)
    setFileData(null)
    setFileName(null)
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const parsed = JSON.parse(ev.target?.result as string)
        if (!parsed.version || !Array.isArray(parsed.feeds)) {
          setFileError('Invalid backup file format.')
          return
        }
        setFileName(file.name)
        setFileData(parsed)
      } catch {
        setFileError('Could not parse file — make sure it is a valid JSON backup.')
      }
    }
    reader.readAsText(file)
  }

  // ── Restore ─────────────────────────────────────────────────────────────────
  const handleRestore = async () => {
    if (!fileData) return
    setShowConfirm(false)
    setRestoring(true)
    setResult(null)
    try {
      const res = await fetch('/api/backup/restore', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify(fileData),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setResult({ ok: false, message: body.detail ?? `Error ${res.status}` })
      } else {
        const body = await res.json()
        setResult({ ok: true, message: `Successfully restored ${body.restored} feed${body.restored !== 1 ? 's' : ''}.` })
        setFileData(null)
        setFileName(null)
        if (fileRef.current) fileRef.current.value = ''
      }
    } catch (err) {
      setResult({ ok: false, message: String(err) })
    } finally {
      setRestoring(false)
    }
  }

  const feedCount = fileData ? (fileData as any).feeds?.length ?? 0 : 0

  return (
    <>
      <PageHeader title="Backup & Restore" description="Export or import all feeds and their scraped items" />

      <div className="mx-auto max-w-lg space-y-6 p-6">

        {/* Export */}
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-1 text-base font-semibold text-gray-800">Export Backup</h2>
          <p className="mb-4 text-sm text-gray-500">
            Downloads a JSON file with all feed configurations and scraped items.
          </p>
          <Button onClick={handleExport}>
            <Download className="h-4 w-4" />
            Download Backup
          </Button>
        </div>

        {/* Restore */}
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-1 text-base font-semibold text-gray-800">Restore Backup</h2>
          <p className="mb-4 text-sm text-gray-500">
            Upload a backup file to restore. <span className="font-medium text-red-600">This will replace all existing feeds and items.</span>
          </p>

          <div className="space-y-4">
            {/* File picker */}
            <div
              onClick={() => fileRef.current?.click()}
              className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-300 px-4 py-8 text-gray-400 transition-colors hover:border-orange-400 hover:text-orange-500"
            >
              <Upload className="h-8 w-8" />
              <span className="text-sm">
                {fileName ? (
                  <span className="font-medium text-gray-700">{fileName}</span>
                ) : (
                  'Click to select a backup file (.json)'
                )}
              </span>
              <input
                ref={fileRef}
                type="file"
                accept=".json,application/json"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>

            {fileError && (
              <p className="flex items-center gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {fileError}
              </p>
            )}

            {fileData && (
              <div className="rounded-md bg-orange-50 px-3 py-2 text-sm text-orange-700">
                <span className="font-medium">{feedCount} feed{feedCount !== 1 ? 's' : ''}</span> found in backup —
                exported on <span className="font-medium">{(fileData as any).exported_at?.slice(0, 10)}</span>
              </div>
            )}

            {result && (
              <p className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm ${result.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
                {result.ok
                  ? <CheckCircle className="h-4 w-4 shrink-0" />
                  : <AlertTriangle className="h-4 w-4 shrink-0" />
                }
                {result.message}
              </p>
            )}

            <Button
              variant="outline"
              disabled={!fileData || restoring}
              loading={restoring}
              onClick={() => setShowConfirm(true)}
            >
              <Upload className="h-4 w-4" />
              Restore Backup
            </Button>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={showConfirm}
        title="Restore backup?"
        description={`This will permanently delete all current feeds and items, then restore ${feedCount} feed${feedCount !== 1 ? 's' : ''} from the backup. This cannot be undone.`}
        confirmLabel="Yes, Restore"
        onConfirm={handleRestore}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  )
}

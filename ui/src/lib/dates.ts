function parseUtc(iso: string): Date {
  // Naive datetime strings from the server (no Z / offset) must be treated as UTC
  if (!iso.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(iso)) {
    return new Date(iso + 'Z')
  }
  return new Date(iso)
}

export function formatRelative(iso: string | null): string {
  if (!iso) return 'Never'
  const date = parseUtc(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60_000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  return parseUtc(iso).toLocaleString()
}

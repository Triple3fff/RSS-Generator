export function getRssUrl(slug: string, publicBaseUrl?: string): string {
  const base = publicBaseUrl ?? window.location.origin
  return `${base}/feed/${slug}.xml`
}

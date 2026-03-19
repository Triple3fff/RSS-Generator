import { apiFetch } from './client'
import type {
  FeedConfig,
  FeedConfigCreate,
  FeedConfigUpdate,
  CreateFeedResponse,
  RawItem,
  ScrapeLog,
} from './types'

export const feedsApi = {
  list: () => apiFetch<FeedConfig[]>('/feeds'),

  get: (id: number) => apiFetch<FeedConfig>(`/feeds/${id}`),

  create: (data: FeedConfigCreate) =>
    apiFetch<CreateFeedResponse>('/feeds', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: number, data: FeedConfigUpdate) =>
    apiFetch<FeedConfig>(`/feeds/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: number) =>
    apiFetch<void>(`/feeds/${id}`, { method: 'DELETE' }),

  triggerScrape: (id: number) =>
    apiFetch<{ message: string }>(`/feeds/${id}/scrape`, { method: 'POST' }),

  preview: (id: number) =>
    apiFetch<RawItem[]>(`/feeds/${id}/preview`),

  logs: (id: number, limit = 20) =>
    apiFetch<ScrapeLog[]>(`/feeds/${id}/logs?limit=${limit}`),

  getConfig: () =>
    apiFetch<{ public_base_url: string }>('/config'),
}

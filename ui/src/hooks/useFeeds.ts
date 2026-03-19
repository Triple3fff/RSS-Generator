import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { feedsApi } from '../api/feeds'
import type { FeedConfigCreate, FeedConfigUpdate } from '../api/types'

export function useFeedList() {
  return useQuery({
    queryKey: ['feeds'],
    queryFn: feedsApi.list,
    refetchInterval: 30_000,
  })
}

export function useFeed(id: number) {
  return useQuery({
    queryKey: ['feeds', id],
    queryFn: () => feedsApi.get(id),
  })
}

export function useCreateFeed() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: FeedConfigCreate) => feedsApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['feeds'] }),
  })
}

export function useUpdateFeed(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: FeedConfigUpdate) => feedsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feeds'] })
      qc.invalidateQueries({ queryKey: ['feeds', id] })
    },
  })
}

export function useDeleteFeed() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => feedsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['feeds'] }),
  })
}

export function useTriggerScrape(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => feedsApi.triggerScrape(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feeds', id] })
      qc.invalidateQueries({ queryKey: ['logs', id] })
    },
  })
}

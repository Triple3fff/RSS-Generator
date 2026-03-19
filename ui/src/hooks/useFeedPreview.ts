import { useQuery } from '@tanstack/react-query'
import { feedsApi } from '../api/feeds'

export function useFeedPreview(id: number, enabled = false) {
  return useQuery({
    queryKey: ['preview', id],
    queryFn: () => feedsApi.preview(id),
    enabled,
    staleTime: 0,
    gcTime: 0,
  })
}

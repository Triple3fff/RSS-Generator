import { useQuery } from '@tanstack/react-query'
import { feedsApi } from '../api/feeds'

export function useFeedLogs(id: number, enabled = true) {
  return useQuery({
    queryKey: ['logs', id],
    queryFn: () => feedsApi.logs(id),
    enabled,
    refetchInterval: 15_000,
  })
}

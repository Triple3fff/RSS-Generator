import { Badge } from '../ui/Badge'
import type { FeedConfig } from '../../api/types'

export function FeedStatusBadge({ feed }: { feed: FeedConfig }) {
  if (!feed.active) return <Badge color="gray">Paused</Badge>
  if (!feed.last_scraped_at) return <Badge color="yellow">Pending</Badge>
  return <Badge color="green">Active</Badge>
}

export interface FeedConfig {
  id: number
  slug: string
  url: string
  title: string
  description: string
  selector_item: string
  selector_title: string
  selector_link: string
  selector_link_attr: string
  selector_description: string | null
  selector_date: string | null
  selector_author: string | null
  date_format: string | null
  poll_interval_minutes: number
  use_playwright: boolean
  keep_html: boolean
  active: boolean
  last_scraped_at: string | null
  created_at: string
  updated_at: string
}

export interface FeedConfigCreate {
  slug: string
  url: string
  title: string
  description?: string
  selector_item: string
  selector_title: string
  selector_link: string
  selector_link_attr?: string
  selector_description?: string
  selector_date?: string
  selector_author?: string
  date_format?: string
  poll_interval_minutes?: number
  use_playwright?: boolean
  keep_html?: boolean
}

export type FeedConfigUpdate = Partial<FeedConfigCreate & { active: boolean }>

export interface RawItem {
  title: string | null
  link: string | null
  description: string | null
  pub_date: string | null
}

export interface CreateFeedResponse {
  feed: FeedConfig
  preview: RawItem[]
}

export interface ScrapeLog {
  id: number
  feed_config_id: number
  success: boolean
  new_items: number
  updated_items: number
  unchanged_items: number
  error_message: string | null
  duration_ms: number | null
  scraped_at: string
}

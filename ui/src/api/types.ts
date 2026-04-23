export interface FeedConfig {
  id: number
  slug: string
  url: string
  title: string
  description: string
  // CSS selectors
  selector_item: string
  selector_title: string
  selector_link: string
  selector_link_attr: string
  selector_description: string | null
  selector_date: string | null
  selector_author: string | null
  selector_item_excluded?: string | null
  date_format: string | null
  // XPath
  use_xpath: boolean
  xpath_item: string | null
  xpath_title: string | null
  xpath_link: string | null
  xpath_link_attr: string
  xpath_description: string | null
  xpath_date: string | null
  xpath_author: string | null
  // Options
  poll_interval_minutes: number
  use_playwright: boolean
  keep_html: boolean
  active: boolean
  label: string | null
  last_scraped_at: string | null
  created_at: string
  updated_at: string
  item_count: number
}

export interface FeedConfigCreate {
  slug: string
  url: string
  title: string
  description?: string
  // CSS selectors
  selector_item: string
  selector_title: string
  selector_link: string
  selector_link_attr?: string
  selector_description?: string
  selector_date?: string
  selector_author?: string
  selector_item_excluded?: string
  date_format?: string
  // XPath
  use_xpath?: boolean
  xpath_item?: string
  xpath_title?: string
  xpath_link?: string
  xpath_link_attr?: string
  xpath_description?: string
  xpath_date?: string
  xpath_author?: string
  // Options
  poll_interval_minutes?: number
  use_playwright?: boolean
  keep_html?: boolean
  label?: string
}

export type FeedConfigUpdate = Omit<Partial<FeedConfigCreate & { active: boolean }>, 'label'> & { label?: string | null }

export interface RawItem {
  title: string | null
  link: string | null
  description: string | null
  pub_date: string | null
  author: string | null
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

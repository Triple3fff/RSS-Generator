from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship


class FeedConfig(SQLModel, table=True):
    __tablename__ = "feed_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True, description="URL-safe identifier used in /feed/{slug}.xml")
    url: str = Field(description="The page URL to scrape")
    title: str = Field(description="RSS channel title")
    description: str = Field(default="", description="RSS channel description")

    # CSS selectors (relative to page root)
    selector_item: str = Field(default="", description="CSS selector for repeating item containers (e.g. 'article.post')")
    selector_title: str = Field(default="", description="CSS selector for title, relative to item container")
    selector_link: str = Field(default="", description="CSS selector for link element (relative to item container). Empty = auto-detect first <a href>.")
    selector_link_attr: str = Field(default="href", description="Attribute to extract from link element")
    selector_description: Optional[str] = Field(default=None, description="CSS selector for description/summary")
    selector_date: Optional[str] = Field(default=None, description="CSS selector for publication date")
    selector_author: Optional[str] = Field(default=None, description="CSS selector for author name")
    selector_item_excluded: Optional[str] = Field(default=None, description="JSON array of link hrefs to exclude from selector_item results")
    date_format: Optional[str] = Field(default=None, description="strptime format for date parsing (e.g. '%Y-%m-%d')")

    # XPath extraction mode (alternative to CSS selectors)
    use_xpath: bool = Field(default=False, description="Use XPath expressions instead of CSS selectors")
    xpath_item: Optional[str] = Field(default=None, description="XPath for repeating item containers (e.g. '//article')")
    xpath_title: Optional[str] = Field(default=None, description="XPath for title, relative to container (e.g. './/h2')")
    xpath_link: Optional[str] = Field(default=None, description="XPath for link element, relative to container (e.g. './/a'). Empty = auto-detect first <a href>.")
    xpath_link_attr: str = Field(default="href", description="Attribute to extract from the XPath link element")
    xpath_description: Optional[str] = Field(default=None, description="XPath for description, relative to container")
    xpath_date: Optional[str] = Field(default=None, description="XPath for date element, relative to container")
    xpath_author: Optional[str] = Field(default=None, description="XPath for author, relative to container")

    # Scraping options
    poll_interval_minutes: int = Field(default=60, description="How often to scrape this page (minutes)")
    use_playwright: bool = Field(default=False, description="Use headless browser for JS-rendered pages")
    playwright_wait_seconds: int = Field(default=0, description="Extra seconds to wait after page load before capturing (Dynamic mode only)")
    keep_html: bool = Field(default=False, description="Preserve HTML tags in description (some readers render it)")
    active: bool = Field(default=True, description="Whether this feed is actively scraped")
    label: Optional[str] = Field(default=None, description="Optional label for grouping feeds")

    # State
    last_scraped_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    items: list["FeedItem"] = Relationship(back_populates="feed_config")
    scrape_logs: list["ScrapeLog"] = Relationship(back_populates="feed_config")


class FeedItem(SQLModel, table=True):
    __tablename__ = "feed_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    feed_config_id: int = Field(foreign_key="feed_configs.id", index=True)

    guid: str = Field(index=True, description="Stable SHA-256 identifier for this item")
    title: Optional[str] = Field(default=None)
    link: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    author: Optional[str] = Field(default=None)
    pub_date: Optional[datetime] = Field(default=None, description="Publication date from the page, if extracted")

    content_hash: str = Field(description="SHA-256 of normalized content, used to detect updates")
    is_new: bool = Field(default=True, description="True until first served in an RSS response")

    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    feed_config: Optional[FeedConfig] = Relationship(back_populates="items")


class ScrapeLog(SQLModel, table=True):
    __tablename__ = "scrape_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    feed_config_id: int = Field(foreign_key="feed_configs.id", index=True)

    success: bool
    new_items: int = Field(default=0)
    updated_items: int = Field(default=0)
    unchanged_items: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)
    duration_ms: Optional[int] = Field(default=None)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    feed_config: Optional[FeedConfig] = Relationship(back_populates="scrape_logs")

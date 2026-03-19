import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, field_validator, model_validator
from sqlmodel import select

from ..api.deps import SessionDep
from ..models.feed import FeedConfig, FeedItem, ScrapeLog
from ..scheduler.jobs import register_feed_job, remove_feed_job, scrape_feed
from ..scraper.extractor import extract_items, SelectorMatchError
from ..scraper.fetcher import fetch_page

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feeds", tags=["feeds"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class FeedConfigCreate(BaseModel):
    slug: str
    url: str
    title: str
    description: str = ""
    # CSS selector fields
    selector_item: str = ""
    selector_title: str = ""
    selector_link: str = ""
    selector_link_attr: str = "href"
    selector_description: Optional[str] = None
    selector_date: Optional[str] = None
    selector_author: Optional[str] = None
    selector_item_excluded: Optional[str] = None
    date_format: Optional[str] = None
    # XPath fields
    use_xpath: bool = False
    xpath_item: Optional[str] = None
    xpath_title: Optional[str] = None
    xpath_link: Optional[str] = None
    xpath_link_attr: str = "href"
    xpath_description: Optional[str] = None
    xpath_date: Optional[str] = None
    xpath_author: Optional[str] = None
    # Options
    poll_interval_minutes: int = 60
    use_playwright: bool = False
    keep_html: bool = False

    @field_validator("slug")
    @classmethod
    def slug_must_be_url_safe(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z0-9-_]+$", v):
            raise ValueError("slug must contain only lowercase letters, digits, hyphens, and underscores")
        return v

    @model_validator(mode="after")
    def check_selectors_for_mode(self) -> "FeedConfigCreate":
        if self.use_xpath:
            if not self.xpath_item:
                raise ValueError("xpath_item is required when use_xpath is True")
            if not self.xpath_title:
                raise ValueError("xpath_title is required when use_xpath is True")
        else:
            if not self.selector_item:
                raise ValueError("selector_item is required when use_xpath is False")
            if not self.selector_title:
                raise ValueError("selector_title is required when use_xpath is False")
        return self


class FeedConfigUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    # CSS
    selector_item: Optional[str] = None
    selector_title: Optional[str] = None
    selector_link: Optional[str] = None
    selector_link_attr: Optional[str] = None
    selector_description: Optional[str] = None
    selector_date: Optional[str] = None
    selector_author: Optional[str] = None
    selector_item_excluded: Optional[str] = None
    date_format: Optional[str] = None
    # XPath
    use_xpath: Optional[bool] = None
    xpath_item: Optional[str] = None
    xpath_title: Optional[str] = None
    xpath_link: Optional[str] = None
    xpath_link_attr: Optional[str] = None
    xpath_description: Optional[str] = None
    xpath_date: Optional[str] = None
    xpath_author: Optional[str] = None
    # Options
    poll_interval_minutes: Optional[int] = None
    use_playwright: Optional[bool] = None
    keep_html: Optional[bool] = None
    active: Optional[bool] = None


class RawItemOut(BaseModel):
    title: Optional[str]
    link: Optional[str]
    description: Optional[str]
    pub_date: Optional[datetime]
    author: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_feed(body: FeedConfigCreate, session: SessionDep, background_tasks: BackgroundTasks):
    """Create a new feed config. Validates selectors by running a test scrape."""
    # Check for duplicate slug
    existing = session.exec(select(FeedConfig).where(FeedConfig.slug == body.slug)).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"A feed with slug '{body.slug}' already exists.")

    # Validate selectors via dry-run
    preview = _dry_run_scrape(body)

    config = FeedConfig(**body.model_dump())
    session.add(config)
    session.commit()
    session.refresh(config)

    # Register scheduler job and trigger immediate first scrape
    register_feed_job(config)
    background_tasks.add_task(scrape_feed, config.id)

    return {"feed": config, "preview": preview}


@router.get("")
def list_feeds(session: SessionDep):
    """List all configured feeds."""
    return session.exec(select(FeedConfig)).all()


@router.get("/{feed_id}")
def get_feed(feed_id: int, session: SessionDep):
    config = session.get(FeedConfig, feed_id)
    if not config:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return config


@router.put("/{feed_id}")
def update_feed(feed_id: int, body: FeedConfigUpdate, session: SessionDep):
    """Update an existing feed config."""
    config = session.get(FeedConfig, feed_id)
    if not config:
        raise HTTPException(status_code=404, detail="Feed not found.")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    config.updated_at = datetime.utcnow()
    session.add(config)
    session.commit()
    session.refresh(config)

    register_feed_job(config)
    return config


@router.delete("/{feed_id}", status_code=204)
def delete_feed(feed_id: int, session: SessionDep):
    """Delete a feed and all its items."""
    config = session.get(FeedConfig, feed_id)
    if not config:
        raise HTTPException(status_code=404, detail="Feed not found.")

    remove_feed_job(feed_id)

    # Cascade delete items and logs
    for item in session.exec(select(FeedItem).where(FeedItem.feed_config_id == feed_id)).all():
        session.delete(item)
    for log in session.exec(select(ScrapeLog).where(ScrapeLog.feed_config_id == feed_id)).all():
        session.delete(log)
    session.delete(config)
    session.commit()


@router.post("/{feed_id}/scrape", status_code=202)
def trigger_scrape(feed_id: int, session: SessionDep, background_tasks: BackgroundTasks):
    """Trigger an immediate scrape for a feed."""
    config = session.get(FeedConfig, feed_id)
    if not config:
        raise HTTPException(status_code=404, detail="Feed not found.")
    background_tasks.add_task(scrape_feed, feed_id)
    return {"message": "Scrape triggered."}


@router.get("/{feed_id}/preview")
def preview_feed(feed_id: int, session: SessionDep):
    """Dry-run scrape to validate selectors without persisting results."""
    config = session.get(FeedConfig, feed_id)
    if not config:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return _dry_run_scrape(config)


@router.get("/{feed_id}/logs")
def get_scrape_logs(feed_id: int, session: SessionDep, limit: int = 20):
    """Get recent scrape logs for a feed."""
    config = session.get(FeedConfig, feed_id)
    if not config:
        raise HTTPException(status_code=404, detail="Feed not found.")
    logs = session.exec(
        select(ScrapeLog)
        .where(ScrapeLog.feed_config_id == feed_id)
        .order_by(ScrapeLog.scraped_at.desc())  # type: ignore[arg-type]
        .limit(limit)
    ).all()
    return logs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dry_run_scrape(config) -> list[RawItemOut]:
    """Fetch and extract without persisting. Raises 422 on selector failure."""
    try:
        result = fetch_page(config.url, use_playwright=config.use_playwright)
        raw_items = extract_items(result, config)
    except SelectorMatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch page: {exc}")

    meaningful = [i for i in raw_items if i.title or i.link]
    return [
        RawItemOut(title=i.title, link=i.link, description=i.description, pub_date=i.pub_date, author=i.author)
        for i in meaningful[:5]
    ]

import logging
from datetime import datetime, timezone

from feedgen.feed import FeedGenerator
from sqlmodel import Session, select

from ..config import settings
from ..models.feed import FeedConfig, FeedItem

logger = logging.getLogger(__name__)


def build_feed(session: Session, config: FeedConfig) -> bytes:
    """Build an RSS 2.0 XML document from persisted FeedItems for the given FeedConfig."""
    items = session.exec(
        select(FeedItem)
        .where(FeedItem.feed_config_id == config.id)
        .order_by(FeedItem.discovered_at.desc())  # type: ignore[arg-type]
        .limit(settings.max_items_per_feed)
    ).all()

    fg = FeedGenerator()
    fg.id(f"{settings.public_base_url}/feed/{config.slug}.xml")
    fg.title(config.title)
    fg.link(href=config.url, rel="alternate")
    fg.link(href=f"{settings.public_base_url}/feed/{config.slug}.xml", rel="self")
    fg.description(config.description or config.title)
    fg.language("en")
    fg.lastBuildDate(_utc_now())

    for item in items:
        fe = fg.add_entry(order="append")
        fe.id(item.guid)
        fe.title(item.title or "(no title)")
        if item.link:
            fe.link(href=item.link)
        if item.description:
            fe.description(item.description)
        if item.author:
            fe.author({"name": item.author})
        pub = item.pub_date or item.discovered_at
        fe.pubDate(_ensure_tz(pub))

    # Mark all is_new items as served
    for item in items:
        if item.is_new:
            item.is_new = False
            session.add(item)
    session.commit()

    xml_bytes: bytes = fg.rss_str(pretty=True)
    logger.debug("Built RSS feed '%s' with %d items", config.slug, len(items))
    return xml_bytes


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ensure_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

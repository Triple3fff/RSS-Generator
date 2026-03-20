import email.utils
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from sqlalchemy import nullslast
from sqlmodel import Session, select

from ..config import settings
from ..models.feed import FeedConfig, FeedItem

logger = logging.getLogger(__name__)


def build_feed(session: Session, config: FeedConfig) -> bytes:
    """Build an RSS 2.0 XML document from persisted FeedItems for the given FeedConfig."""
    items = session.exec(
        select(FeedItem)
        .where(FeedItem.feed_config_id == config.id)
        .order_by(nullslast(FeedItem.pub_date.desc()), FeedItem.discovered_at.desc(), FeedItem.id.asc())  # type: ignore[arg-type]
        .limit(settings.max_items_per_feed)
    ).all()

    feed_url = f"{settings.public_base_url}/feed/{config.slug}.xml"

    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(
        '<rss version="2.0"'
        ' xmlns:atom="http://www.w3.org/2005/Atom"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
    )
    parts.append("  <channel>")
    parts.append(f"    <title>{_x(config.title)}</title>")
    parts.append(f"    <link>{_x(config.url)}</link>")
    parts.append(f"    <description>{_x(config.description or config.title)}</description>")
    parts.append("    <language>en</language>")
    parts.append(f"    <lastBuildDate>{_rfc822(_utc_now())}</lastBuildDate>")
    parts.append("    <generator>RSS Generator</generator>")
    parts.append(
        f'    <atom:link href="{_x(feed_url)}" rel="self" type="application/rss+xml"/>'
    )

    # Build a title→link map so linkless duplicates can borrow the link from their
    # linked counterpart (arises when the same article was stored twice before dedup fix)
    title_to_link: dict[str, str] = {
        item.title: item.link
        for item in items
        if item.title and item.link
    }
    seen_titles: set[str] = set()

    for item in items:
        if not item.title and not item.link:
            continue
        # Deduplicate: skip if we already emitted an item with this title
        if item.title:
            if item.title in seen_titles:
                continue
            seen_titles.add(item.title)

        effective_link = item.link or title_to_link.get(item.title or "")

        parts.append("    <item>")
        title = item.title or _title_from_url(effective_link)
        if title:
            parts.append(f"      <title>{_x(title)}</title>")
        if effective_link:
            parts.append(f"      <link>{_x(effective_link)}</link>")
        if item.description:
            parts.append(f"      <description>{_x(item.description)}</description>")
        # guid is a SHA-256 hash, not a URL — isPermaLink must be false
        parts.append(f'      <guid isPermaLink="false">{_x(item.guid)}</guid>')
        pub = item.pub_date or item.discovered_at
        parts.append(f"      <pubDate>{_rfc822(_ensure_tz(pub))}</pubDate>")
        if item.author:
            # RSS 2.0 <author> requires an email; use dc:creator for plain names
            parts.append(f"      <dc:creator>{_x(item.author)}</dc:creator>")
        parts.append("    </item>")

    parts.append("  </channel>")
    parts.append("</rss>")

    # Mark all is_new items as served
    for item in items:
        if item.is_new:
            item.is_new = False
            session.add(item)
    session.commit()

    xml_str = "\n".join(parts)
    logger.debug("Built RSS feed '%s' with %d items", config.slug, len(items))
    return xml_str.encode("utf-8")


def _title_from_url(url: Optional[str]) -> Optional[str]:
    """Derive a readable title from the URL slug when no scraped title is available.
    e.g. /tip/Top-AWS-tools-for-cloud-cost-forecasting → 'Top AWS tools for cloud cost forecasting'"""
    if not url:
        return None
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    if not slug:
        return None
    # Strip common file extensions
    if "." in slug:
        slug = slug.rsplit(".", 1)[0]
    title = slug.replace("-", " ").replace("_", " ").strip()
    return title or None


def _x(text: str) -> str:
    """XML-escape a string value."""
    return escape(text)


def _rfc822(dt: datetime) -> str:
    """Format a datetime as RFC 822, as required by RSS 2.0."""
    return email.utils.format_datetime(dt)


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ensure_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

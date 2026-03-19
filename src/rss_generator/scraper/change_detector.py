import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from ..models.feed import FeedConfig, FeedItem
from .extractor import RawItem

logger = logging.getLogger(__name__)


@dataclass
class ChangeReport:
    new_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0


def _make_guid(feed_url: str, item: RawItem) -> str:
    """Stable identifier for an item based on its feed and link/title."""
    key = f"{feed_url}|{item.link or item.title or ''}"
    return hashlib.sha256(key.encode()).hexdigest()


def _make_content_hash(item: RawItem) -> str:
    """Hash of item content to detect updates."""
    content = f"{item.title}|{item.link}|{item.description}"
    return hashlib.sha256(content.encode()).hexdigest()


def detect_changes(session: Session, config: FeedConfig, raw_items: list[RawItem]) -> ChangeReport:
    """Compare newly scraped items against persisted FeedItems, inserting/updating as needed."""
    # Load existing items for this feed, indexed by guid
    existing: dict[str, FeedItem] = {
        row.guid: row
        for row in session.exec(
            select(FeedItem).where(FeedItem.feed_config_id == config.id)
        ).all()
    }

    report = ChangeReport()

    for raw in raw_items:
        guid = _make_guid(config.url, raw)
        content_hash = _make_content_hash(raw)

        if guid not in existing:
            # New item — insert
            item = FeedItem(
                feed_config_id=config.id,
                guid=guid,
                title=raw.title,
                link=raw.link,
                description=raw.description,
                author=raw.author,
                pub_date=raw.pub_date,
                content_hash=content_hash,
                is_new=True,
                discovered_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(item)
            report.new_count += 1
            logger.debug("New item: %s", raw.title or raw.link)

        elif existing[guid].content_hash != content_hash:
            # Changed item — update
            db_item = existing[guid]
            db_item.title = raw.title
            db_item.link = raw.link
            db_item.description = raw.description
            db_item.author = raw.author
            if raw.pub_date:
                db_item.pub_date = raw.pub_date
            db_item.content_hash = content_hash
            db_item.updated_at = datetime.utcnow()
            session.add(db_item)
            report.updated_count += 1
            logger.debug("Updated item: %s", raw.title or raw.link)

        else:
            report.unchanged_count += 1

    session.commit()
    logger.info(
        "Feed %s — new: %d, updated: %d, unchanged: %d",
        config.slug, report.new_count, report.updated_count, report.unchanged_count,
    )
    return report

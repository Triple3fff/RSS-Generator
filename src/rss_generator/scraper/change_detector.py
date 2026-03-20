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


def _deduplicate_raw(raw_items: list[RawItem]) -> list[RawItem]:
    """Within a single scrape batch, collapse same-title duplicates into one item.
    When the same title appears with and without a link, keep the version with the link."""
    best_by_title: dict[str, RawItem] = {}
    titleless: list[RawItem] = []

    for raw in raw_items:
        if not raw.title and not raw.link:
            continue
        if not raw.title:
            titleless.append(raw)
            continue
        prev = best_by_title.get(raw.title)
        if prev is None or (raw.link and not prev.link):
            best_by_title[raw.title] = raw

    return list(best_by_title.values()) + titleless


def detect_changes(session: Session, config: FeedConfig, raw_items: list[RawItem]) -> ChangeReport:
    """Compare newly scraped items against persisted FeedItems, inserting/updating as needed."""
    # Collapse same-title duplicates before hitting the DB
    raw_items = _deduplicate_raw(raw_items)

    # Load existing items indexed by guid and by title
    all_existing = session.exec(
        select(FeedItem).where(FeedItem.feed_config_id == config.id)
    ).all()
    existing: dict[str, FeedItem] = {row.guid: row for row in all_existing}
    # Secondary index by title for merging linkless→linked transitions
    existing_by_title: dict[str, FeedItem] = {
        row.title: row for row in all_existing if row.title
    }

    report = ChangeReport()
    seen_guids: set[str] = set()

    for raw in raw_items:
        if not raw.title and not raw.link:
            continue

        guid = _make_guid(config.url, raw)
        if guid in seen_guids:
            continue
        seen_guids.add(guid)

        content_hash = _make_content_hash(raw)

        if guid in existing:
            db_item = existing[guid]
            if db_item.content_hash != content_hash or (
                db_item.title is None and raw.title is not None
            ):
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

        else:
            # Check if the same article exists under a different GUID (e.g., was stored
            # without a link before, so its GUID was title-based; now we have a link)
            merge_target = existing_by_title.get(raw.title) if raw.title else None
            if merge_target and raw.link and not merge_target.link:
                # Same article, now discovered with a link — update in place
                merge_target.link = raw.link
                merge_target.description = raw.description or merge_target.description
                merge_target.author = raw.author or merge_target.author
                if raw.pub_date:
                    merge_target.pub_date = raw.pub_date
                merge_target.content_hash = content_hash
                merge_target.guid = guid  # update GUID to the now-stable link-based value
                merge_target.updated_at = datetime.utcnow()
                session.add(merge_target)
                # Keep indexes consistent
                existing[guid] = merge_target
                report.updated_count += 1
                logger.debug("Merged linkless item with link: %s", raw.title)
            else:
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

    session.commit()
    logger.info(
        "Feed %s — new: %d, updated: %d, unchanged: %d",
        config.slug, report.new_count, report.updated_count, report.unchanged_count,
    )
    return report

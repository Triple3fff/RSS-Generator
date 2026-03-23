import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import select, text

from ..api.deps import SessionDep
from ..models.feed import FeedConfig, FeedItem, ScrapeLog
from ..scheduler.jobs import register_feed_job, remove_feed_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/backup", tags=["backup"])

BACKUP_VERSION = 1


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("")
def export_backup(session: SessionDep):
    """Export all feed configs and items as a downloadable JSON backup."""
    configs = session.exec(select(FeedConfig)).all()
    feeds = []
    for config in configs:
        items = session.exec(
            select(FeedItem).where(FeedItem.feed_config_id == config.id)
        ).all()
        feeds.append({
            "config": _serialize(config),
            "items": [_serialize(item) for item in items],
        })

    payload = {
        "version": BACKUP_VERSION,
        "exported_at": datetime.utcnow().isoformat(),
        "feeds": feeds,
    }
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": 'attachment; filename="rss_backup.json"'},
    )


# ── Restore ───────────────────────────────────────────────────────────────────

class RestoreRequest(BaseModel):
    version: int
    feeds: list[dict[str, Any]]


@router.post("/restore", status_code=200)
def restore_backup(body: RestoreRequest, session: SessionDep):
    """Wipe all existing feeds and restore from a backup payload."""
    if body.version != BACKUP_VERSION:
        raise HTTPException(status_code=400, detail=f"Unsupported backup version: {body.version}")

    # Remove all scheduler jobs first
    existing_configs = session.exec(select(FeedConfig)).all()
    for config in existing_configs:
        try:
            remove_feed_job(config.id)
        except Exception:
            pass

    # Wipe all existing data (order matters for FK constraints)
    session.exec(text("DELETE FROM scrape_logs"))   # type: ignore[call-overload]
    session.exec(text("DELETE FROM feed_items"))    # type: ignore[call-overload]
    session.exec(text("DELETE FROM feed_configs"))  # type: ignore[call-overload]
    session.commit()

    restored_configs: list[FeedConfig] = []

    for entry in body.feeds:
        raw_config = entry.get("config", {})
        raw_items = entry.get("items", [])

        # Strip relationship fields and re-insert
        config_data = {k: v for k, v in raw_config.items() if k not in ("items", "scrape_logs")}
        _parse_datetimes(config_data, ["last_scraped_at", "created_at", "updated_at"])

        config = FeedConfig(**config_data)
        session.add(config)
        session.flush()  # get the new id

        for raw_item in raw_items:
            item_data = {k: v for k, v in raw_item.items() if k not in ("feed_config",)}
            item_data["feed_config_id"] = config.id
            _parse_datetimes(item_data, ["pub_date", "discovered_at", "updated_at"])
            item_data.pop("id", None)  # let SQLite assign new id
            session.add(FeedItem(**item_data))

        restored_configs.append(config)

    session.commit()

    # Re-register scheduler jobs for active feeds
    for config in restored_configs:
        session.refresh(config)
        if config.active:
            register_feed_job(config)

    logger.info("Restored %d feeds from backup", len(restored_configs))
    return {"restored": len(restored_configs)}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize(obj) -> dict:
    """Convert a SQLModel instance to a plain dict (datetime → ISO string)."""
    result = {}
    for key, val in obj.__dict__.items():
        if key.startswith("_"):
            continue
        if isinstance(val, datetime):
            result[key] = val.isoformat()
        else:
            result[key] = val
    return result


def _parse_datetimes(data: dict, fields: list[str]) -> None:
    """Parse ISO datetime strings in-place for the given fields."""
    for field in fields:
        val = data.get(field)
        if isinstance(val, str):
            try:
                data[field] = datetime.fromisoformat(val)
            except ValueError:
                data[field] = None

import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select

from ..models.database import engine
from ..models.feed import FeedConfig, ScrapeLog
from ..scraper.fetcher import fetch_page
from ..scraper.extractor import extract_items, SelectorMatchError
from ..scraper.change_detector import detect_changes

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(
    job_defaults={"misfire_grace_time": 300, "coalesce": True},
    timezone="UTC",
)


def scrape_feed(feed_config_id: int) -> None:
    """Execute a full scrape cycle for a single FeedConfig."""
    start = time.monotonic()
    with Session(engine) as session:
        config = session.get(FeedConfig, feed_config_id)
        if config is None or not config.active:
            return

        success = False
        error_msg = None
        report = None

        try:
            result = fetch_page(config.url, use_playwright=config.use_playwright)
            raw_items = extract_items(result, config)
            report = detect_changes(session, config, raw_items)
            success = True
        except SelectorMatchError as exc:
            error_msg = f"Selector error: {exc}"
            logger.warning("Feed '%s': %s", config.slug, error_msg)
        except Exception as exc:
            error_msg = str(exc)
            logger.exception("Feed '%s' scrape failed: %s", config.slug, exc)

        duration_ms = int((time.monotonic() - start) * 1000)

        # Update last_scraped_at
        config.last_scraped_at = datetime.utcnow()
        config.updated_at = datetime.utcnow()
        session.add(config)

        # Persist scrape log
        log = ScrapeLog(
            feed_config_id=feed_config_id,
            success=success,
            new_items=report.new_count if report else 0,
            updated_items=report.updated_count if report else 0,
            unchanged_items=report.unchanged_count if report else 0,
            error_message=error_msg,
            duration_ms=duration_ms,
        )
        session.add(log)
        session.commit()

        # Prune logs beyond the 20 most recent for this feed
        all_logs = session.exec(
            select(ScrapeLog)
            .where(ScrapeLog.feed_config_id == feed_config_id)
            .order_by(ScrapeLog.scraped_at.desc())  # type: ignore[arg-type]
        ).all()
        for old_log in all_logs[20:]:
            session.delete(old_log)
        if all_logs[20:]:
            session.commit()


def register_feed_job(config: FeedConfig) -> None:
    """Add or replace a scheduler job for a FeedConfig."""
    job_id = f"feed_{config.id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        scrape_feed,
        trigger=IntervalTrigger(minutes=config.poll_interval_minutes),
        args=[config.id],
        id=job_id,
        replace_existing=True,
    )
    logger.info("Registered job '%s' (every %d min)", job_id, config.poll_interval_minutes)


def remove_feed_job(feed_config_id: int) -> None:
    """Remove the scheduler job for a FeedConfig."""
    job_id = f"feed_{feed_config_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("Removed job '%s'", job_id)


def load_all_jobs() -> None:
    """Called on app startup: register jobs for all active feeds."""
    with Session(engine) as session:
        configs = session.exec(select(FeedConfig).where(FeedConfig.active == True)).all()  # noqa: E712
    for config in configs:
        register_feed_job(config)
    logger.info("Loaded %d feed jobs", len(configs))

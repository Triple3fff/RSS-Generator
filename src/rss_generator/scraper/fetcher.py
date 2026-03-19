import logging
from dataclasses import dataclass
from datetime import datetime

import requests
import requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import settings

logger = logging.getLogger(__name__)

# Cache HTTP responses to avoid re-fetching within the same poll window
requests_cache.install_cache(
    "data/http_cache",
    backend="sqlite",
    expire_after=max(60, settings.default_poll_interval_minutes * 60 - 60),
)


@dataclass
class FetchResult:
    html: str
    status_code: int
    fetched_at: datetime
    final_url: str


def _build_session() -> requests.Session:
    session = requests_cache.CachedSession(
        "data/http_cache",
        backend="sqlite",
        expire_after=max(60, settings.default_poll_interval_minutes * 60 - 60),
    )
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": settings.user_agent})
    return session


def fetch_page(url: str, use_playwright: bool = False) -> FetchResult:
    """Fetch a web page and return its HTML content."""
    if use_playwright:
        return _fetch_with_playwright(url)
    return _fetch_with_requests(url)


def _fetch_with_requests(url: str) -> FetchResult:
    session = _build_session()
    response = session.get(url, timeout=settings.request_timeout_seconds, allow_redirects=True)
    response.raise_for_status()
    logger.debug("Fetched %s → %d (%s)", url, response.status_code, response.url)
    return FetchResult(
        html=response.text,
        status_code=response.status_code,
        fetched_at=datetime.utcnow(),
        final_url=response.url,
    )


def _fetch_with_playwright(url: str) -> FetchResult:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=settings.user_agent)
        page.goto(url, timeout=settings.request_timeout_seconds * 1000)
        page.wait_for_load_state("networkidle")
        html = page.content()
        final_url = page.url
        browser.close()

    return FetchResult(
        html=html,
        status_code=200,
        fetched_at=datetime.utcnow(),
        final_url=final_url,
    )

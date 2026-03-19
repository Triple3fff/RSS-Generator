import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from ..models.feed import FeedConfig
from .fetcher import FetchResult

logger = logging.getLogger(__name__)


class SelectorMatchError(ValueError):
    """Raised when a required CSS selector matches no elements."""


@dataclass
class RawItem:
    title: Optional[str]
    link: Optional[str]
    description: Optional[str]
    pub_date: Optional[datetime]
    author: Optional[str] = None


def extract_items(result: FetchResult, config: FeedConfig) -> list[RawItem]:
    """Apply CSS selectors from FeedConfig to extracted HTML and return structured items."""
    soup = BeautifulSoup(result.html, "lxml")
    containers = soup.select(config.selector_item)

    if not containers:
        raise SelectorMatchError(
            f"selector_item '{config.selector_item}' matched 0 elements on {result.final_url}"
        )

    items = []
    for container in containers:
        title = _extract_text(container, config.selector_title)
        if config.selector_link:
            link = _extract_link(container, config.selector_link, config.selector_link_attr, result.final_url)
        else:
            link = _auto_detect_link(container, result.final_url)
        description = _extract_description(container, config.selector_description, config.keep_html)
        pub_date = _extract_date(container, config.selector_date, config.date_format)
        author = _extract_text(container, config.selector_author) if config.selector_author else None
        items.append(RawItem(title=title, link=link, description=description, pub_date=pub_date, author=author))

    logger.debug("Extracted %d items from %s", len(items), result.final_url)
    return items


def _extract_text(container, selector: Optional[str]) -> Optional[str]:
    if not selector:
        return None
    el = container.select_one(selector)
    if el is None:
        return None
    return el.get_text(strip=True) or None


def _extract_link(container, selector: str, attr: str, base_url: str) -> Optional[str]:
    el = container.select_one(selector)
    if el is None:
        return None
    href = el.get(attr)
    if not href:
        return None
    return urljoin(base_url, str(href))


def _auto_detect_link(container, base_url: str) -> Optional[str]:
    for a in container.find_all("a", href=True):
        href = str(a.get("href", "")).strip()
        if href and href != "#" and not href.startswith(("javascript:", "mailto:", "tel:")):
            return urljoin(base_url, href)
    return None


def _extract_description(container, selector: Optional[str], keep_html: bool) -> Optional[str]:
    if not selector:
        return None
    el = container.select_one(selector)
    if el is None:
        return None
    if keep_html:
        return str(el) or None
    return el.get_text(separator=" ", strip=True) or None


def _extract_date(container, selector: Optional[str], date_format: Optional[str]) -> Optional[datetime]:
    if not selector:
        return None
    el = container.select_one(selector)
    if el is None:
        return None

    # Try the datetime attribute first (common in <time> elements)
    raw = el.get("datetime") or el.get_text(strip=True)
    if not raw:
        return None

    if date_format:
        try:
            return datetime.strptime(raw, date_format)
        except ValueError:
            logger.debug("strptime failed for '%s' with format '%s', falling back to dateutil", raw, date_format)

    try:
        return dateutil_parser.parse(raw)
    except (ValueError, OverflowError):
        logger.debug("dateutil could not parse date: '%s'", raw)
        return None

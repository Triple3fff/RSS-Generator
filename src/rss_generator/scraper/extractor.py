import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import lxml.html
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from ..models.feed import FeedConfig
from .fetcher import FetchResult

logger = logging.getLogger(__name__)


class SelectorMatchError(ValueError):
    """Raised when a required CSS selector or XPath expression matches no elements."""


@dataclass
class RawItem:
    title: Optional[str]
    link: Optional[str]
    description: Optional[str]
    pub_date: Optional[datetime]
    author: Optional[str] = None


def extract_items(result: FetchResult, config: FeedConfig) -> list[RawItem]:
    """Dispatch to XPath or CSS extraction based on config.use_xpath."""
    if config.use_xpath:
        return _extract_items_xpath(result, config)
    return _extract_items_css(result, config)


# ── CSS extraction (BeautifulSoup) ────────────────────────────────────────────

def _extract_items_css(result: FetchResult, config: FeedConfig) -> list[RawItem]:
    """Apply CSS selectors from FeedConfig to extracted HTML and return structured items."""
    soup = BeautifulSoup(result.html, "lxml")
    containers = soup.select(config.selector_item)

    # Apply href-based exclusions (set by the visual picker)
    if config.selector_item_excluded:
        try:
            import json as _json
            excluded_hrefs = set(_json.loads(config.selector_item_excluded))
            if excluded_hrefs:
                filtered = []
                for c in containers:
                    link = None
                    for a in c.find_all("a", href=True):
                        href = str(a.get("href", "")).strip()
                        if href and href != "#" and not href.startswith(("javascript:", "mailto:", "tel:")):
                            link = urljoin(result.final_url, href)
                            break
                    if link not in excluded_hrefs:
                        filtered.append(c)
                containers = filtered
        except Exception:
            pass

    if not containers:
        raise SelectorMatchError(
            f"selector_item '{config.selector_item}' matched 0 elements on {result.final_url}"
        )

    items = []
    for container in containers:
        title = _css_text(container, config.selector_title)
        if config.selector_link:
            link = _css_link(container, config.selector_link, config.selector_link_attr, result.final_url)
        else:
            link = None
        # If no selector_link or it didn't match, auto-detect link and try anchor text as title hint
        if link is None:
            link, _auto_title = _css_auto_link_with_text(container, result.final_url)
            if title is None:
                title = _auto_title
        # Universal fallback: scan all anchors for the first one with non-empty text
        if title is None:
            _, title = _css_auto_link_with_text(container, result.final_url)
        # Ancestor fallback: if still no link, check if container itself or a parent
        # is an <a href> or carries a data-* link attribute.
        if link is None:
            cur = container
            for _ in range(4):
                if cur.name in ("a", "article", "div", "li", "section"):
                    # Standard href (only useful on <a>)
                    if cur.name == "a":
                        link = _resolve_href(str(cur.get("href", "")), result.final_url)
                    # data-* fallback on any element
                    if link is None:
                        for attr in _DATA_LINK_ATTRS:
                            link = _resolve_href(str(cur.get(attr, "")), result.final_url)
                            if link:
                                break
                    if link:
                        break
                cur = cur.parent
                if cur is None or cur.name in ("body", "html", "[document]"):
                    break
        if title is None and config.selector_title:
            logger.warning(
                "selector_title '%s' matched nothing in a container on %s — "
                "check that the selector is relative to the item container",
                config.selector_title, result.final_url,
            )
        description = _css_description(container, config.selector_description, config.keep_html)
        pub_date = _css_date(container, config.selector_date, config.date_format)
        author = _css_text(container, config.selector_author) if config.selector_author else None
        if author:
            author = author.rstrip(',').strip() or None
        items.append(RawItem(title=title, link=link, description=description, pub_date=pub_date, author=author))

    logger.debug("Extracted %d items (CSS) from %s", len(items), result.final_url)
    return items


def _css_text(container, selector: Optional[str]) -> Optional[str]:
    if not selector:
        return None
    el = container.select_one(selector)
    if el is None:
        return None
    return el.get_text(strip=True) or None


def _css_link(container, selector: str, attr: str, base_url: str) -> Optional[str]:
    el = container.select_one(selector)
    if el is None:
        return None
    href = el.get(attr)
    if not href:
        return None
    return urljoin(base_url, str(href))


def _css_auto_link(container, base_url: str) -> Optional[str]:
    url, _ = _css_auto_link_with_text(container, base_url)
    return url


_DATA_LINK_ATTRS = ("data-href", "data-url", "data-link", "data-target")


def _resolve_href(raw: str, base_url: str) -> Optional[str]:
    """Return an absolute URL or None for blank / javascript: / anchor-only hrefs."""
    raw = raw.strip()
    if not raw or raw == "#" or raw.startswith(("javascript:", "mailto:", "tel:")):
        return None
    return urljoin(base_url, raw)


def _css_auto_link_with_text(container, base_url: str) -> tuple[Optional[str], Optional[str]]:
    """Return (absolute_url, link_text) scanning all valid anchors in the container.
    URL = first valid anchor; text = first anchor that has non-empty visible text.
    These may be different elements (e.g. when the first anchor wraps only an image).

    Falls back to data-href / data-url / data-link / data-target attributes on
    <a> elements (common when href="javascript:void(0)") and then on any element
    in the container (clickable <div>/<article> cards).
    """
    first_url: Optional[str] = None
    first_text: Optional[str] = None

    # Pass 1: standard <a href> — also check data-* when href is unusable
    for a in container.find_all("a"):
        href = str(a.get("href", "")).strip()
        url = _resolve_href(href, base_url)
        if url is None:
            # href is blank or javascript: — try data-* attributes on the same element
            for attr in _DATA_LINK_ATTRS:
                val = str(a.get(attr, "")).strip()
                url = _resolve_href(val, base_url)
                if url:
                    break
        if url:
            if first_url is None:
                first_url = url
            if first_text is None:
                text = a.get_text(strip=True)
                if text:
                    first_text = text
            if first_url and first_text:
                break

    # Pass 2: data-* link attributes on any element in the container
    # (handles clickable <div>/<article>/<li> cards with no <a> child)
    if first_url is None:
        for attr in _DATA_LINK_ATTRS:
            for el in container.find_all(attrs={attr: True}):
                url = _resolve_href(str(el.get(attr, "")), base_url)
                if url:
                    first_url = url
                    if first_text is None:
                        first_text = el.get_text(strip=True) or None
                    break
            if first_url:
                break

    return first_url, first_text


def _css_description(container, selector: Optional[str], keep_html: bool) -> Optional[str]:
    if not selector:
        return None
    el = container.select_one(selector)
    if el is None:
        return None
    if keep_html:
        return str(el) or None
    return el.get_text(separator=" ", strip=True) or None


def _css_date(container, selector: Optional[str], date_format: Optional[str]) -> Optional[datetime]:
    if not selector:
        return None
    el = container.select_one(selector)
    if el is None:
        return None
    raw = el.get("datetime") or el.get_text(strip=True)
    if not raw:
        return None
    return _parse_date(raw, date_format)


# ── XPath extraction (lxml.html) ──────────────────────────────────────────────

def _extract_items_xpath(result: FetchResult, config: FeedConfig) -> list[RawItem]:
    """Apply XPath expressions from FeedConfig to parsed HTML and return structured items."""
    tree = lxml.html.fromstring(result.html)

    containers = tree.xpath(config.xpath_item)
    if not containers:
        raise SelectorMatchError(
            f"xpath_item '{config.xpath_item}' matched 0 elements on {result.final_url}"
        )

    # Apply href-based exclusions (set by the visual picker)
    if config.selector_item_excluded:
        try:
            import json as _json
            excluded_hrefs = set(_json.loads(config.selector_item_excluded))
            if excluded_hrefs:
                filtered = []
                for c in containers:
                    link = None
                    for a in c.xpath('.//a[@href]'):
                        href = str(a.get("href", "")).strip()
                        if href and href != "#" and not href.startswith(("javascript:", "mailto:", "tel:")):
                            link = urljoin(result.final_url, href)
                            break
                    if link not in excluded_hrefs:
                        filtered.append(c)
                containers = filtered
        except Exception:
            pass

    items = []
    for container in containers:
        title = _xpath_text(container, config.xpath_title)
        if config.xpath_link:
            link = _xpath_link(container, config.xpath_link, config.xpath_link_attr or "href", result.final_url)
        else:
            link = None
        if link is None:
            link, _auto_title = _xpath_auto_link_with_text(container, result.final_url)
            if title is None:
                title = _auto_title
        if title is None:
            _, title = _xpath_auto_link_with_text(container, result.final_url)
        # Ancestor fallback: if still no link, check if container itself or a parent
        # is an <a href> or carries a data-* link attribute.
        if link is None:
            cur = container
            for _ in range(4):
                tag = cur.tag if hasattr(cur, "tag") else None
                if tag == "a":
                    link = _resolve_href(str(cur.get("href", "")), result.final_url)
                if link is None and tag in ("a", "article", "div", "li", "section"):
                    for attr in _DATA_LINK_ATTRS:
                        link = _resolve_href(str(cur.get(attr, "")), result.final_url)
                        if link:
                            break
                if link:
                    break
                cur = cur.getparent()
                if cur is None or (hasattr(cur, "tag") and cur.tag in ("body", "html")):
                    break
        description = _xpath_description(container, config.xpath_description, config.keep_html)
        pub_date = _xpath_date(container, config.xpath_date, config.date_format)
        author = _xpath_text(container, config.xpath_author) if config.xpath_author else None
        if author:
            author = author.rstrip(',').strip() or None
        items.append(RawItem(title=title, link=link, description=description, pub_date=pub_date, author=author))

    logger.debug("Extracted %d items (XPath) from %s", len(items), result.final_url)
    return items


def _xpath_text(container, xpath: Optional[str]) -> Optional[str]:
    if not xpath:
        return None
    results = container.xpath(xpath)
    if not results:
        return None
    first = results[0]
    if isinstance(first, str):
        return first.strip() or None
    # lxml element — get all text content
    return first.text_content().strip() or None


def _xpath_link(container, xpath: str, attr: str, base_url: str) -> Optional[str]:
    results = container.xpath(xpath)
    if not results:
        return None
    first = results[0]
    if isinstance(first, str):
        # XPath pointed directly at an attribute value (e.g. './/a/@href')
        return urljoin(base_url, first.strip()) if first.strip() else None
    # lxml element — extract the named attribute
    href = first.get(attr)
    if not href:
        return None
    return urljoin(base_url, str(href))


def _xpath_auto_link(container, base_url: str) -> Optional[str]:
    url, _ = _xpath_auto_link_with_text(container, base_url)
    return url


def _xpath_auto_link_with_text(container, base_url: str) -> tuple[Optional[str], Optional[str]]:
    """Return (absolute_url, link_text) scanning all valid anchors in the container.
    URL = first valid anchor; text = first anchor that has non-empty visible text.
    Falls back to data-href / data-url / data-link / data-target attributes."""
    first_url: Optional[str] = None
    first_text: Optional[str] = None

    # Pass 1: standard <a href> — also check data-* when href is unusable
    for a in container.xpath('.//a'):
        href = str(a.get("href", "")).strip()
        url = _resolve_href(href, base_url)
        if url is None:
            for attr in _DATA_LINK_ATTRS:
                val = str(a.get(attr, "")).strip()
                url = _resolve_href(val, base_url)
                if url:
                    break
        if url:
            if first_url is None:
                first_url = url
            if first_text is None:
                text = a.text_content().strip()
                if text:
                    first_text = text
            if first_url and first_text:
                break

    # Pass 2: data-* on any element
    if first_url is None:
        for attr in _DATA_LINK_ATTRS:
            for el in container.xpath(f'.//*[@{attr}]'):
                url = _resolve_href(str(el.get(attr, "")), base_url)
                if url:
                    first_url = url
                    if first_text is None:
                        first_text = el.text_content().strip() or None
                    break
            if first_url:
                break

    return first_url, first_text


def _xpath_description(container, xpath: Optional[str], keep_html: bool) -> Optional[str]:
    if not xpath:
        return None
    results = container.xpath(xpath)
    if not results:
        return None
    first = results[0]
    if isinstance(first, str):
        return first.strip() or None
    if keep_html:
        return lxml.html.tostring(first, encoding="unicode") or None
    return first.text_content().strip() or None


def _xpath_date(container, xpath: Optional[str], date_format: Optional[str]) -> Optional[datetime]:
    if not xpath:
        return None
    results = container.xpath(xpath)
    if not results:
        return None
    first = results[0]
    if isinstance(first, str):
        raw = first.strip()
    else:
        # Prefer the datetime attribute (common on <time> elements)
        raw = first.get("datetime") or first.text_content().strip()
    if not raw:
        return None
    return _parse_date(raw, date_format)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _parse_date(raw: str, date_format: Optional[str]) -> Optional[datetime]:
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

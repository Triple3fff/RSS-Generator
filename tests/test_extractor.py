from datetime import datetime

import pytest

from rss_generator.scraper.extractor import extract_items, SelectorMatchError, RawItem
from rss_generator.scraper.fetcher import FetchResult
from rss_generator.models.feed import FeedConfig

BASE_CONFIG = dict(
    id=1,
    slug="test",
    url="https://example.com",
    title="Test",
    description="",
    selector_item="article",
    selector_title="h2",
    selector_link="a",
    selector_link_attr="href",
    selector_description="p",
    selector_date=None,
    date_format=None,
    poll_interval_minutes=60,
    use_playwright=False,
    keep_html=False,
    active=True,
)

SAMPLE_HTML = """
<html><body>
  <article>
    <h2>Title One</h2>
    <a href="/post/1">Read more</a>
    <p>Description one.</p>
  </article>
  <article>
    <h2>Title Two</h2>
    <a href="https://other.com/post/2">Read more</a>
    <p>Description two.</p>
  </article>
</body></html>
"""


def _make_result(html: str, url: str = "https://example.com") -> FetchResult:
    return FetchResult(html=html, status_code=200, fetched_at=datetime.utcnow(), final_url=url)


def _make_config(**overrides) -> FeedConfig:
    data = {**BASE_CONFIG, **overrides}
    return FeedConfig(**data)


def test_extracts_two_items():
    config = _make_config()
    result = _make_result(SAMPLE_HTML)
    items = extract_items(result, config)
    assert len(items) == 2


def test_extracts_title():
    config = _make_config()
    items = extract_items(_make_result(SAMPLE_HTML), config)
    assert items[0].title == "Title One"
    assert items[1].title == "Title Two"


def test_resolves_relative_link():
    config = _make_config()
    items = extract_items(_make_result(SAMPLE_HTML), config)
    assert items[0].link == "https://example.com/post/1"


def test_preserves_absolute_link():
    config = _make_config()
    items = extract_items(_make_result(SAMPLE_HTML), config)
    assert items[1].link == "https://other.com/post/2"


def test_extracts_description():
    config = _make_config()
    items = extract_items(_make_result(SAMPLE_HTML), config)
    assert items[0].description == "Description one."


def test_raises_on_no_item_match():
    config = _make_config(selector_item=".nonexistent")
    with pytest.raises(SelectorMatchError, match="matched 0 elements"):
        extract_items(_make_result(SAMPLE_HTML), config)


def test_missing_optional_selector_returns_none():
    config = _make_config(selector_description=None)
    items = extract_items(_make_result(SAMPLE_HTML), config)
    assert items[0].description is None


def test_date_extraction_with_time_element():
    html = """
    <html><body>
      <article>
        <h2>Dated Post</h2>
        <a href="/p">Link</a>
        <time datetime="2024-06-15">June 15</time>
      </article>
    </body></html>
    """
    config = _make_config(selector_date="time")
    items = extract_items(_make_result(html), config)
    assert items[0].pub_date is not None
    assert items[0].pub_date.year == 2024
    assert items[0].pub_date.month == 6


def test_keep_html_preserves_tags():
    config = _make_config(keep_html=True)
    items = extract_items(_make_result(SAMPLE_HTML), config)
    assert "<p>" in items[0].description

import logging
from dataclasses import dataclass
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    html: str
    status_code: int
    fetched_at: datetime
    final_url: str


def _build_session() -> requests.Session:
    session = requests.Session()
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
    if use_playwright and settings.playwright_enabled:
        try:
            return _fetch_with_playwright(url)
        except RuntimeError as exc:
            logger.warning("Playwright unavailable (%s), falling back to requests for %s", exc, url)
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

    _COOKIE_SELECTORS = [
        "#onetrust-accept-btn-handler",
        ".cc-accept", ".cc-btn.cc-allow", ".cc-btn.cc-dismiss",
        "[aria-label*='accept' i]", "[aria-label*='agree' i]", "[aria-label*='dismiss' i]",
        "button[id*='accept' i]", "button[id*='agree' i]", "button[id*='cookie' i]",
        "button[class*='accept' i]", "button[class*='agree' i]",
        "[data-testid*='accept' i]", "[data-action*='accept' i]",
    ]

    with sync_playwright() as p:
        # Do NOT pass the custom user_agent — sites like Azure check for
        # non-browser UAs (e.g. "RSSGenerator/1.0") and return empty/restricted
        # content.  Let Playwright use its bundled Chromium's real UA instead.
        # Also disable the AutomationControlled feature flag and clear the
        # navigator.webdriver property so bot-detection CDNs treat the request
        # as a normal browser visit.
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        # Patch fingerprint properties checked by Cloudflare and similar CDNs
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver',  {get: () => undefined});
            Object.defineProperty(navigator, 'plugins',    {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages',  {get: () => ['en-US','en']});
            window.chrome = window.chrome || { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
        """)
        page = context.new_page()
        page.goto(url, timeout=settings.request_timeout_seconds * 1000)
        page.wait_for_load_state("networkidle")

        # ── Step 1: dismiss cookie / consent popups BEFORE scrolling ────────
        # A consent banner covering the viewport blocks IntersectionObserver
        # callbacks for anything behind it, so lazy-loaded article cards never
        # trigger if we scroll first and dismiss second.
        _COOKIE_SELECTORS_EXPANDED = _COOKIE_SELECTORS + [
            "#CybotCookiebotDialogBodyButtonAccept",
            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
            "#BorlabsCookieBtn--acceptAll",
            "button[data-borlabs-cookie-accept]",
            "#cmplz-accept", ".cmplz-accept",
            "#cn-accept-cookie", ".cn-set-cookie",
            "#wt-cli-accept-all-btn",
            "#cookie_action_close_header",
            ".cli-accept",
        ]
        dismissed = False
        for css in _COOKIE_SELECTORS_EXPANDED:
            try:
                el = page.query_selector(css)
                if el and el.is_visible():
                    el.click()
                    dismissed = True
                    break
            except Exception:
                pass
        if not dismissed:
            import re as _re
            _accept_rx = _re.compile(
                r'\b(accept all|accept cookies|accept everything|allow all|allow cookies|agree|i agree|ok|got it|confirm|continue)\b',
                _re.IGNORECASE,
            )
            for btn in page.query_selector_all("button, a[role='button'], input[type='button'], input[type='submit']"):
                try:
                    text = (btn.inner_text() or btn.get_attribute("value") or "").strip()
                    if _accept_rx.search(text) and btn.is_visible():
                        btn.click()
                        break
                except Exception:
                    pass

        # ── Step 2: incremental scroll to trigger lazy / infinite-scroll content
        # 300 ms per step gives each batch of cards enough time to fetch and
        # render before we move to the next viewport position.
        viewport_h = page.evaluate("window.innerHeight") or 900
        total_h = page.evaluate("document.body.scrollHeight") or 0
        pos = 0
        while pos < total_h:
            pos = min(pos + max(viewport_h // 2, 400), total_h)
            page.evaluate(f"window.scrollTo(0, {pos})")
            page.wait_for_timeout(300)
            new_h = page.evaluate("document.body.scrollHeight") or 0
            if new_h > total_h:
                total_h = new_h
        # Extra pause after reaching the bottom so the last batch can finish rendering
        page.wait_for_timeout(1500)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass  # best-effort — some pages never reach networkidle after scroll
        page.evaluate("window.scrollTo(0, 0)")  # back to top for the visual selector

        html = page.content()
        final_url = page.url
        context.close()
        browser.close()

    return FetchResult(
        html=html,
        status_code=200,
        fetched_at=datetime.utcnow(),
        final_url=final_url,
    )

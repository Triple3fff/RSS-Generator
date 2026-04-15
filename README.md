# RSS Generator

Turn any website into an RSS feed — no coding required.

RSS Generator lets you follow websites that don't publish RSS feeds, using your favourite RSS reader (Readwise Reader, Feedly, Inoreader, and others). You point it at a page, pick which elements to track, and it scrapes the page on a schedule and serves the results as a standard RSS feed.

---

## What it does

- **Scrapes any website** on a configurable schedule (default: every 60 minutes).
- **Visual Picker** — load the target page inside the app, click the elements you want, and the CSS selectors are filled in for you automatically.
- **Full item extraction** — captures title, link, description, author, and publication date.
- **Change detection** — only new items are added to the feed; duplicates are silently skipped.
- **Headless browser support** — enable Playwright per-feed to handle JavaScript-rendered pages.
- **Backup & Restore** — export and import all your feed configurations in one click.
- **Secure** — login-protected dashboard; RSS feed URLs are public so your reader can subscribe.

---

## How to use it

### 1. Log in

Open the app in your browser and log in with your credentials.  
Default credentials on a fresh install: **Admin / Temporal** — change the password immediately after first login.

### 2. Add a feed

1. Click **New Feed**.
2. Paste the URL of the page you want to monitor [Click in **Source URL**].
3. Give the feed a name and optionally a slug (used in the feed URL) [Click in **Title**].

### 3. Pick the CSS selectors (what you want to convert to RSS in the Web page)

Click **Open Visual Picker**. The target page loads inside the app. Click on:

- An **item** (e.g. an article card, a list row) — this defines what counts as one feed entry.
- The **title** inside that item.
- The **link** inside that item.
- Optionally: a **description**, **date**, and **author**.

The selectors are filled in automatically. Hit **Save**.

> **Tip:** If the page looks empty or broken in the picker, toggle **Use Playwright** (headless browser) — this is needed for sites that render content with JavaScript.

### 4. Subscribe in your RSS reader

After saving, the feed's RSS URL appears at the top of the feed detail page. It looks like:

```
https://your-domain.com/feed/your-feed-slug.xml
```

Copy this URL and add it to your RSS reader.

### 5. Force a scrape

Click **Scrape now** on any feed to fetch the latest content immediately, without waiting for the next scheduled run.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `/data` | Directory for the SQLite database. Must be a persistent volume. |
| `DATABASE_URL` | *(derived from DATA_DIR)* | Full SQLAlchemy database URL — override if using a different database. |
| `JWT_SECRET` | *(required)* | Secret key for signing login tokens. Set a long random string. |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Base URL used in feed `<link>` elements (set to your public domain). |
| `PLAYWRIGHT_ENABLED` | `false` | Set to `true` to enable headless browser support for JS-rendered pages. |
| `DEFAULT_POLL_INTERVAL_MINUTES` | `60` | How often feeds are scraped by default. |
| `SERVER_HOST` | `0.0.0.0` | Host to bind to. |
| `SERVER_PORT` | `8000` | Port to bind to. |

---

## Known limitations

- **JavaScript-rendered pages** require `PLAYWRIGHT_ENABLED=true` and the Playwright Chromium browser installed in the container. This increases memory usage significantly.
- **Login sessions** are JWT tokens with a fixed expiry — there is currently no "remember me" option.
- **RSS feed visibility** — feed XML endpoints are public (no authentication), so anyone who knows the URL can subscribe. If you need private feeds, put the app behind a reverse proxy with access control.
- **Single-user** — there is one set of admin credentials. Multi-user access is not currently supported.
- **SQLite only** — the app uses SQLite by default. It is well-suited for personal or small-team use; it is not designed for high-concurrency production deployments.

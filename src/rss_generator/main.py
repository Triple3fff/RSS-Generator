import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import settings
from .models.database import init_db
from .scheduler.jobs import scheduler, load_all_jobs
from .api import feeds as feeds_router
from .api import serve as serve_router
from .api import picker as picker_router
from .api import auth as auth_router
from .api.auth import verify_token

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Path to the React build output (ui/dist), relative to this file
UI_DIST = Path(__file__).parents[2] / "ui" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    init_db()

    logger.info("Starting scheduler...")
    scheduler.start()
    load_all_jobs()

    yield

    # Shutdown
    logger.info("Stopping scheduler...")
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="RSS Generator",
    description=(
        "Monitors web pages for updates and generates RSS feeds from user-defined CSS selectors. "
        "Compatible with Readwise, Feedly, and Inoreader."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for local React dev server (Vite on port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://www.rss-feeder.win"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def restrict_external_to_feeds(request: Request, call_next):
    """Block external (Cloudflare-proxied) requests to anything except /feed/* paths."""
    is_external = "cf-connecting-ip" in request.headers
    if is_external and not request.url.path.startswith("/feed/"):
        return Response(status_code=404)
    return await call_next(request)

# Auth router (public — login endpoint must be unprotected)
app.include_router(auth_router.router)
# API routes mounted under /api (protected)
app.include_router(feeds_router.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(picker_router.router, dependencies=[Depends(verify_token)])
# RSS feed URLs stay at root level: /feed/{slug}.xml
app.include_router(serve_router.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/api/config", tags=["config"])
def get_config():
    """Expose server config values needed by the frontend."""
    return {"public_base_url": settings.public_base_url}


# Serve React SPA (only if ui/dist exists — i.e. after `npm run build`)
if UI_DIST.is_dir():
    assets_dir = UI_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        # Don't intercept API or RSS routes
        if full_path.startswith(("api/", "feed/", "health")):
            raise HTTPException(status_code=404)
        index = UI_DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        raise HTTPException(status_code=404)


def run():
    uvicorn.run(
        "rss_generator.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
    )


if __name__ == "__main__":
    run()

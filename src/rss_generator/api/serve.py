from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlmodel import select

from ..api.deps import SessionDep
from ..feeds.builder import build_feed
from ..models.feed import FeedConfig

router = APIRouter(tags=["rss"])


@router.get("/feed/{slug}.xml", response_class=Response)
def serve_feed(slug: str, session: SessionDep):
    """Serve the RSS 2.0 XML feed for the given slug."""
    config = session.exec(select(FeedConfig).where(FeedConfig.slug == slug)).first()
    if not config:
        raise HTTPException(status_code=404, detail=f"No feed found with slug '{slug}'.")

    if config.last_scraped_at is None:
        raise HTTPException(
            status_code=503,
            detail="This feed has not been scraped yet. Please wait a moment and try again.",
        )

    xml_bytes = build_feed(session, config)

    return Response(
        content=xml_bytes,
        media_type="application/rss+xml; charset=utf-8",
        headers={"Cache-Control": "max-age=300"},
    )

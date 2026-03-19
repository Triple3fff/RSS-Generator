import xml.etree.ElementTree as ET
from datetime import datetime

import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from rss_generator.models.feed import FeedConfig, FeedItem
from rss_generator.feeds.builder import build_feed


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def populated_feed(db_session) -> FeedConfig:
    config = FeedConfig(
        slug="my-feed",
        url="https://example.com",
        title="My Feed",
        description="A test feed",
        selector_item="article",
        selector_title="h2",
        selector_link="a",
        last_scraped_at=datetime.utcnow(),
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)

    for i in range(3):
        item = FeedItem(
            feed_config_id=config.id,
            guid=f"guid-{i}",
            title=f"Post {i}",
            link=f"https://example.com/post/{i}",
            description=f"Description {i}",
            content_hash=f"hash-{i}",
        )
        db_session.add(item)
    db_session.commit()
    return config


def test_valid_xml(db_session, populated_feed):
    xml_bytes = build_feed(db_session, populated_feed)
    root = ET.fromstring(xml_bytes)
    assert root.tag == "rss"
    assert root.attrib.get("version") == "2.0"


def test_channel_title(db_session, populated_feed):
    xml_bytes = build_feed(db_session, populated_feed)
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    assert channel.find("title").text == "My Feed"


def test_item_count(db_session, populated_feed):
    xml_bytes = build_feed(db_session, populated_feed)
    root = ET.fromstring(xml_bytes)
    items = root.findall("channel/item")
    assert len(items) == 3


def test_items_have_guid_and_pubdate(db_session, populated_feed):
    xml_bytes = build_feed(db_session, populated_feed)
    root = ET.fromstring(xml_bytes)
    for item in root.findall("channel/item"):
        assert item.find("guid") is not None
        assert item.find("pubDate") is not None


def test_is_new_cleared_after_build(db_session, populated_feed):
    build_feed(db_session, populated_feed)
    from sqlmodel import select
    items = db_session.exec(select(FeedItem)).all()
    assert all(not item.is_new for item in items)

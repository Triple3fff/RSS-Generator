from datetime import datetime

import pytest
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from rss_generator.models.feed import FeedConfig, FeedItem
from rss_generator.scraper.change_detector import detect_changes, ChangeReport
from rss_generator.scraper.extractor import RawItem


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
def config(db_session) -> FeedConfig:
    cfg = FeedConfig(
        slug="test",
        url="https://example.com",
        title="Test",
        selector_item="article",
        selector_title="h2",
        selector_link="a",
    )
    db_session.add(cfg)
    db_session.commit()
    db_session.refresh(cfg)
    return cfg


def _raw(title="Post", link="https://example.com/post", desc="body"):
    return RawItem(title=title, link=link, description=desc, pub_date=None)


def test_new_item_inserted(db_session, config):
    report = detect_changes(db_session, config, [_raw()])
    assert report.new_count == 1
    assert report.updated_count == 0
    items = db_session.exec(select(FeedItem)).all()
    assert len(items) == 1
    assert items[0].is_new is True


def test_unchanged_item_not_duplicated(db_session, config):
    detect_changes(db_session, config, [_raw()])
    report = detect_changes(db_session, config, [_raw()])
    assert report.unchanged_count == 1
    assert len(db_session.exec(select(FeedItem)).all()) == 1


def test_updated_item_detected(db_session, config):
    detect_changes(db_session, config, [_raw(desc="original")])
    report = detect_changes(db_session, config, [_raw(desc="updated content")])
    assert report.updated_count == 1
    item = db_session.exec(select(FeedItem)).first()
    assert item.description == "updated content"


def test_multiple_items(db_session, config):
    items = [
        _raw(title="A", link="https://example.com/a"),
        _raw(title="B", link="https://example.com/b"),
        _raw(title="C", link="https://example.com/c"),
    ]
    report = detect_changes(db_session, config, items)
    assert report.new_count == 3
    assert len(db_session.exec(select(FeedItem)).all()) == 3

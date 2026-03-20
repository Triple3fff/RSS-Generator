import re
from sqlmodel import SQLModel, create_engine, Session, text
from ..config import settings

# connect_args required for SQLite multi-thread safety with FastAPI
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


def init_db() -> None:
    """Create all tables if they don't exist, and run column migrations."""
    SQLModel.metadata.create_all(engine)
    _migrate(engine)


def _migrate(engine) -> None:
    """Add new columns to existing tables without dropping data."""
    _clean_picker_classes(engine)
    migrations = [
        "ALTER TABLE feed_configs ADD COLUMN selector_author TEXT",
        "ALTER TABLE feed_items ADD COLUMN author TEXT",
        # XPath support
        "ALTER TABLE feed_configs ADD COLUMN use_xpath INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE feed_configs ADD COLUMN xpath_item TEXT",
        "ALTER TABLE feed_configs ADD COLUMN xpath_title TEXT",
        "ALTER TABLE feed_configs ADD COLUMN xpath_link TEXT",
        "ALTER TABLE feed_configs ADD COLUMN xpath_link_attr TEXT NOT NULL DEFAULT 'href'",
        "ALTER TABLE feed_configs ADD COLUMN xpath_description TEXT",
        "ALTER TABLE feed_configs ADD COLUMN xpath_date TEXT",
        "ALTER TABLE feed_configs ADD COLUMN xpath_author TEXT",
        "ALTER TABLE feed_configs ADD COLUMN selector_item_excluded TEXT",
        "ALTER TABLE feed_configs ADD COLUMN label TEXT",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists


def _clean_picker_classes(engine) -> None:
    """Remove picker-injected CSS classes (e.g. .__ph) that were accidentally baked into selectors."""
    selector_cols = [
        "selector_item", "selector_title", "selector_link",
        "selector_description", "selector_date", "selector_author",
    ]
    pattern = re.compile(r'\.__ph[a-z]*')
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, " + ", ".join(selector_cols) + " FROM feed_configs")).fetchall()
        for row in rows:
            feed_id = row[0]
            updates = {}
            for i, col in enumerate(selector_cols):
                val = row[i + 1]
                if val and pattern.search(val):
                    updates[col] = pattern.sub('', val).strip()
            if updates:
                set_sql = ", ".join(f"{k} = :{k}" for k in updates)
                updates["id"] = feed_id
                conn.execute(text(f"UPDATE feed_configs SET {set_sql} WHERE id = :id"), updates)
        conn.commit()


def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session

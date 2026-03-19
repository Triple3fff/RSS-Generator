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
    migrations = [
        "ALTER TABLE feed_configs ADD COLUMN selector_author TEXT",
        "ALTER TABLE feed_items ADD COLUMN author TEXT",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists


def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session

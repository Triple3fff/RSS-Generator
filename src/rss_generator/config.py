import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Persistent data directory — survives container restarts on IONOS and similar platforms.
# Override with the DATA_DIR environment variable; defaults to /data.
_data_dir = os.environ.get("DATA_DIR", "/data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Database — path is derived from DATA_DIR so data survives restarts.
    # Override by setting DATABASE_URL explicitly.
    database_url: str = f"sqlite:///{os.path.join(_data_dir, 'rss_generator.db')}"

    # Feed defaults
    default_poll_interval_minutes: int = 60
    max_items_per_feed: int = 200

    # HTTP scraping
    request_timeout_seconds: int = 30
    user_agent: str = "Mozilla/5.0 (compatible; RSSGenerator/1.0)"

    # Playwright (optional)
    playwright_enabled: bool = False

    # Public base URL for feed links served to external readers
    public_base_url: str = "http://localhost:8000"

    jwt_secret: str = ""


settings = Settings()

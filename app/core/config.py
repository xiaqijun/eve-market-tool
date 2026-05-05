"""Application configuration via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = dict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = (
        "postgresql+asyncpg://eve_market:eve_market_dev@localhost:5432/eve_market"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ESI API
    esi_user_agent: str = "EVE-Market-Tool/1.0 (https://github.com/your/repo)"
    esi_base_url: str = "https://esi.evetech.net/latest"

    # Security
    secret_key: str = "change-me-to-a-random-secret-string"

    # EVE SSO
    eve_client_id: str = ""
    eve_client_secret: str = ""
    eve_callback_url: str = "http://localhost:8000/api/v1/auth/callback"

    # Scheduler
    scheduler_enabled: bool = True
    market_fetch_interval_minutes: int = 5

    # SDE
    sde_path: str = ""  # optional path to SDE SQLite file

    # Hub regions to track
    hub_region_ids: list[int] = [10000002, 10000043, 10000032, 10000030, 10000042]

    @property
    def is_dev(self) -> bool:
        return self.secret_key == "change-me-to-a-random-secret-string"


settings = Settings()

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLACKBOX_", env_file=".env", extra="ignore"
    )

    database_url: str = "sqlite:///./data/blackbox.db"
    cors_origins: str = "http://localhost:3000"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    #: Upload size cap in megabytes; long recordings may need more.
    max_upload_mb: int = 20
    #: Comma-separated API tokens. Empty (the default) disables auth,
    #: matching the documented trusted-network deployment model.
    api_tokens: str = ""
    #: Rolling pre-failure window kept per streaming robot, in seconds.
    stream_window_s: float = 600.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def api_token_list(self) -> list[str]:
        return [t.strip() for t in self.api_tokens.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

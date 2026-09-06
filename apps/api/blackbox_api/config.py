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
    #: Comma-separated tokens limited to read-only (GET) routes — for
    #: wallboards and dashboards that should not be able to mutate data.
    readonly_tokens: str = ""
    #: JSON object mapping token -> facility name; each token reads and
    #: writes only that facility's incidents (per-fleet isolation).
    facility_tokens: str = ""
    #: Rolling pre-failure window kept per streaming robot, in seconds.
    stream_window_s: float = 600.0
    #: Optional webhook POSTed for every ingested incident (best-effort).
    webhook_url: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def api_token_list(self) -> list[str]:
        return [t.strip() for t in self.api_tokens.split(",") if t.strip()]

    @property
    def readonly_api_token_list(self) -> list[str]:
        return [
            t.strip() for t in self.readonly_tokens.split(",") if t.strip()
        ]

    @property
    def facility_token_map(self) -> dict[str, str]:
        if not self.facility_tokens.strip():
            return {}
        import json

        try:
            parsed = json.loads(self.facility_tokens)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "BLACKBOX_FACILITY_TOKENS must be a JSON object mapping "
                "token to facility name"
            ) from exc
        if not isinstance(parsed, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and k and v
            for k, v in parsed.items()
        ):
            raise ValueError(
                "BLACKBOX_FACILITY_TOKENS must map non-empty token strings "
                "to non-empty facility names"
            )
        return parsed


@lru_cache
def get_settings() -> Settings:
    return Settings()

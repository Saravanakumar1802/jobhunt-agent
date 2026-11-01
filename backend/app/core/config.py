"""Central configuration loaded from environment variables / `.env`.

Every tunable (quotas, cache TTL, model chains, batch sizes) lives here so the
cost-optimisation knobs are visible in one place.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default free-tier model chains, highest priority first. They can be changed at
# runtime from the Models page (stored in Mongo), so a retired model never
# requires a code change.
DEFAULT_SMALL_MODELS = [
    "groq/openai/gpt-oss-20b",
    "gemini/gemini-2.5-flash-lite",
    "openrouter/openai/gpt-oss-20b:free",
]
DEFAULT_MID_MODELS = [
    "groq/openai/gpt-oss-120b",
    "gemini/gemini-2.5-flash",
    "openrouter/openai/gpt-oss-120b:free",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Job Hunt Copilot"
    env: str = "dev"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rate_limit_enabled: bool = True

    # Database — empty URI switches to the in-memory store (dev/demo only).
    mongodb_uri: str = ""
    mongodb_db: str = "job_copilot"

    # Auth
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # LLM providers (free tiers only)
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # Job sources
    rapidapi_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # Free-tier quotas (monthly). JSearch's live remaining count from the
    # response headers takes precedence when available.
    jsearch_monthly_quota: int = 200
    adzuna_monthly_quota: int = 2500
    remotive_monthly_quota: int = 120
    arbeitnow_monthly_quota: int = 1000

    # Cost-optimisation knobs
    search_cache_ttl_hours: int = 6
    prefilter_top_k: int = 12
    analyzer_batch_size: int = 4
    matcher_batch_size: int = 4
    llm_concurrency: int = 3
    llm_timeout_seconds: int = 45
    llm_cooldown_seconds: int = 60
    jd_max_chars: int = 4500
    model_health_interval_hours: int = 6
    http_timeout_seconds: float = 20.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_memory_db(self) -> bool:
        return not self.mongodb_uri


@lru_cache
def get_settings() -> Settings:
    return Settings()

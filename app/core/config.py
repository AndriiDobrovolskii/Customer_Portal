from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/customer_portal"
    argon2_time_cost: int = 3
    argon2_memory_cost_kb: int = 65536
    argon2_parallelism: int = 4
    verification_token_ttl_hours: int = 24
    resend_cooldown_seconds: int = 60
    unverified_account_purge_after_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()

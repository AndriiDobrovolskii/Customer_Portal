from functools import lru_cache

from pydantic import SecretStr
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
    # Dev-only default; every real deployment MUST override this via env.
    jwt_secret_key: SecretStr = SecretStr("dev-only-insecure-secret-change-me")
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    email_change_token_ttl_hours: int = 24
    valkey_url: str = "redis://localhost:6379/0"
    login_failure_threshold_account: int = 10
    login_failure_threshold_ip: int = 20
    login_throttle_window_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000
    password_reset_token_ttl_minutes: int = 30
    password_reset_cooldown_seconds: int = 60
    password_reset_account_hourly_limit: int = 5
    password_reset_ip_hourly_limit: int = 10
    breached_password_list_path: str = "app/core/data/common_passwords.txt"  # noqa: S105
    perm_epoch_ttl_seconds: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()

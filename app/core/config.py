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
    # Dev-only default (base64-encoded 32 raw bytes); every real deployment
    # MUST override this via env, same discipline as jwt_secret_key (OD-2).
    mfa_secret_encryption_key: SecretStr = SecretStr("ZGV2LW9ubHktaW5zZWN1cmUtbWZhLWtleS0zMmJ5dGU=")
    mfa_token_ttl_seconds: int = 300
    mfa_verify_lockout_threshold: int = 5
    mfa_grace_period_days: int = 14
    max_live_sessions_per_user: int = 20
    # US-2.6/OD-4: the .mmdb file is fetched at build/deploy time (via a
    # MaxMind license key held by the deploy pipeline, never by this app's
    # own runtime config - the app only needs to know where to find the
    # already-fetched file). Absent in local dev/CI is expected;
    # app/core/geoip.py degrades to returning no location rather than
    # failing.
    geoip_database_path: str = "app/core/data/GeoLite2-City.mmdb"
    invitation_token_ttl_hours: int = 24
    invitation_resend_hourly_limit: int = 5
    # OD-2: no assignment concept exists yet, so every unassigned ticket's
    # customer-reply notification (FR-2) goes to this one shared address.
    support_queue_email: str = "support-queue@portal.internal"
    # US-4.2 Architectural Change #12: the connection string the running
    # application uses to serve requests (non-superuser app_runtime role),
    # distinct from `database_url` (which narrows to "the migration/owner
    # role's URL"). Dev-only default; every real deployment MUST override
    # this via env, same discipline as jwt_secret_key.
    runtime_database_url: str = (
        "postgresql+asyncpg://app_runtime:CHANGE_ME_IN_PRODUCTION@localhost:5432/customer_portal"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

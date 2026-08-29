from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/customer_portal"
    bcrypt_rounds: int = 12


@lru_cache
def get_settings() -> Settings:
    return Settings()

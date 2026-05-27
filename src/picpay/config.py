from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development")
    app_name: str = Field(default="picpay-desafio-backend")
    log_level: str = Field(default="INFO")

    database_url: str = Field(
        default="postgresql+psycopg://picpay:picpay@localhost:5432/picpay"
    )

    authorizer_url: str = Field(default="https://util.devi.tools/api/v2/authorize")
    authorizer_timeout: float = Field(default=5.0)

    notifier_url: str = Field(default="https://util.devi.tools/api/v1/notify")
    notifier_timeout: float = Field(default=5.0)
    notifier_max_attempts: int = Field(default=3)


@lru_cache
def get_settings() -> Settings:
    return Settings()

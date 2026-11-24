"""Typed application configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HERBIE_",
        extra="ignore",
        case_sensitive=False,
        frozen=True,
    )

    environment: str = "local"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    database_url: str = "postgresql+asyncpg://herbie:local_only@localhost:5432/herbie"
    amqp_url: str = "amqp://herbie:local_only@localhost:5672/%2F"
    mqtt_host: str = "localhost"
    mqtt_port: int = Field(default=1883, ge=1, le=65535)

    dynamodb_endpoint: str | None = "http://localhost:8001"
    dynamodb_region: str = "us-east-1"
    s3_endpoint: str | None = "http://localhost:9000"
    s3_bucket: str = "herbie-raw-local"


@lru_cache
def get_settings() -> Settings:
    """Return one immutable settings view per process."""

    return Settings()

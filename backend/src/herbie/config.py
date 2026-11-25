"""Typed application configuration."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
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
    amqp_prefetch: int = Field(default=100, ge=1, le=10_000)
    telemetry_max_payload_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    telemetry_max_future_skew_seconds: int = Field(default=300, ge=0, le=86_400)
    telemetry_retry_limit: int = Field(default=3, ge=0, le=20)
    telemetry_retry_delay_ms: int = Field(default=5_000, ge=100, le=3_600_000)
    telemetry_shutdown_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    registered_devices: tuple[str, ...] = ()
    worker_role: Literal["telemetry", "archive"] = "telemetry"
    mqtt_host: str = "localhost"
    mqtt_port: int = Field(default=1883, ge=1, le=65535)

    dynamodb_endpoint: str | None = "http://localhost:8001"
    dynamodb_region: str = "us-east-1"
    dynamodb_telemetry_table: str = "herbie-telemetry-local"
    telemetry_event_retention_days: int = Field(default=14, ge=1, le=365)
    telemetry_replay_retention_days: int = Field(default=180, ge=180, le=3_650)
    s3_endpoint: str | None = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "herbie-raw-local"
    s3_kms_key_id: str | None = None
    s3_allow_unsupported_public_access_block: bool = False
    archive_flush_interval_seconds: float = Field(default=5.0, gt=0, le=3_600)
    archive_batch_limit: int = Field(default=1_000, ge=1, le=10_000)

    @model_validator(mode="after")
    def validate_telemetry_retention(self) -> Self:
        if self.telemetry_replay_retention_days <= self.telemetry_event_retention_days:
            raise ValueError("telemetry replay retention must exceed event retention")
        for entry in self.registered_devices:
            parts = entry.split("/")
            if len(parts) != 2 or not all(parts):
                raise ValueError(
                    "registered devices must use '<tenant UUID>/<charger UUID>' entries"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return one immutable settings view per process."""

    return Settings()

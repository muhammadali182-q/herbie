"""Versioned MQTT contracts for charger telemetry."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageType(StrEnum):
    """Message types currently accepted by the telemetry path."""

    TELEMETRY_REPORTED = "telemetry.reported"


class ChargerStatus(StrEnum):
    """Simplified operational state reported by a charger."""

    AVAILABLE = "available"
    CHARGING = "charging"
    FAULTED = "faulted"
    OFFLINE = "offline"


class TelemetryPayload(BaseModel):
    """Cumulative energy and instantaneous charger measurements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cumulative_energy_wh: int = Field(ge=0)
    power_w: int = Field(ge=0)
    status: ChargerStatus
    voltage_v: int | None = Field(default=None, ge=0, le=1_000)
    current_ma: int | None = Field(default=None, ge=0)


class TelemetryEvent(BaseModel):
    """Immutable protocol envelope for a telemetry reading."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(pattern=r"^1\.0$")
    message_id: UUID
    message_type: MessageType
    occurred_at: datetime
    sent_at: datetime
    boot_id: UUID
    sequence: int = Field(ge=0)
    tenant_id: UUID
    charger_id: UUID
    connector_id: int = Field(ge=1, le=64)
    payload: TelemetryPayload

    @field_validator("occurred_at", "sent_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject ambiguous timestamps at the protocol boundary."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset")
        return value

    def canonical_json(self) -> str:
        """Return a stable representation for idempotency collision checks."""

        return self.model_dump_json(exclude_none=True)

    @classmethod
    def from_json(cls, raw: bytes | str) -> Self:
        """Validate a raw MQTT payload."""

        return cls.model_validate_json(raw)

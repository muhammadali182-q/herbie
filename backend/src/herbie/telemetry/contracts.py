"""Versioned MQTT contracts for charger telemetry."""

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    cumulative_energy_wh: int = Field(ge=0, le=10**15)
    power_w: int = Field(ge=0, le=1_000_000)
    status: ChargerStatus
    voltage_v: int | None = Field(default=None, ge=0, le=1_000)
    current_ma: int | None = Field(default=None, ge=0, le=5_000_000)


class TelemetryEvent(BaseModel):
    """Immutable protocol envelope for a telemetry reading."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: str = Field(pattern=r"^1\.0$")
    message_id: UUID
    message_type: MessageType
    occurred_at: datetime
    sent_at: datetime
    boot_id: UUID
    boot_started_at: datetime
    sequence: int = Field(ge=0, le=2**63 - 1)
    tenant_id: UUID
    charger_id: UUID
    connector_id: int = Field(ge=1, le=64)
    payload: TelemetryPayload

    @field_validator("message_id", "boot_id", "tenant_id", "charger_id", mode="before")
    @classmethod
    def require_canonical_uuid(cls, value: Any) -> UUID:
        """Accept UUID objects internally and canonical lowercase strings on wire."""

        if isinstance(value, UUID):
            return value
        if not isinstance(value, str):
            raise ValueError("identifier must be a canonical UUID string")
        try:
            parsed = UUID(value)
        except ValueError as error:
            raise ValueError("identifier must be a canonical UUID string") from error
        if str(parsed) != value:
            raise ValueError("identifier must use canonical lowercase UUID form")
        return parsed

    @field_validator("occurred_at", "sent_at", "boot_started_at", mode="before")
    @classmethod
    def require_rfc3339_timezone(cls, value: Any) -> datetime:
        """Reject numeric/naive timestamps and normalize accepted values to UTC."""

        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("timestamp must be RFC 3339 with a timezone offset") from error
        elif isinstance(value, datetime):
            parsed = value
        else:
            raise ValueError("timestamp must be RFC 3339 text")
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset")
        return parsed.astimezone(UTC)

    @model_validator(mode="after")
    def validate_temporal_order(self) -> Self:
        if self.boot_started_at > self.occurred_at:
            raise ValueError("boot_started_at cannot follow occurred_at")
        if self.sent_at < self.occurred_at:
            raise ValueError("sent_at cannot precede occurred_at")
        return self

    def canonical_json(self) -> str:
        """Return a stable representation for idempotency collision checks."""

        return json.dumps(
            self.model_dump(mode="json", exclude_none=True),
            sort_keys=True,
            separators=(",", ":"),
        )

    def semantic_fingerprint(self) -> str:
        """Return a versioned content fingerprint for replay conflict checks."""

        canonical = f"herbie-telemetry-v1\0{self.canonical_json()}".encode()
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def from_json(cls, raw: bytes | str) -> Self:
        """Validate a raw MQTT payload."""

        return cls.model_validate_json(raw)

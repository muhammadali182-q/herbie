"""Application service for validated, idempotent telemetry ingestion."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from herbie.telemetry.contracts import TelemetryEvent
from herbie.telemetry.errors import TelemetryClockSkewError, TopicIdentityMismatchError
from herbie.telemetry.repository import StoredTelemetry, TelemetryRepository
from herbie.telemetry.topic import DeviceIdentity, TelemetryTopic


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Public ingestion outcome used by workers and metrics."""

    accepted: bool
    duplicate: bool
    latest_updated: bool
    telemetry: StoredTelemetry


class TelemetryIngestionService:
    """Validate trusted identity and coordinate hot/archive writes."""

    def __init__(
        self,
        repository: TelemetryRepository,
        clock: Callable[[], datetime] | None = None,
        max_future_skew: timedelta = timedelta(minutes=5),
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_future_skew = max_future_skew

    async def ingest(
        self,
        identity: DeviceIdentity,
        topic: str,
        raw_payload: bytes | str,
    ) -> IngestionResult:
        topic_identity = TelemetryTopic.parse(topic)
        event = TelemetryEvent.from_json(raw_payload)
        if (
            identity.tenant_id != topic_identity.tenant_id
            or identity.charger_id != topic_identity.charger_id
            or event.tenant_id != topic_identity.tenant_id
            or event.charger_id != topic_identity.charger_id
        ):
            raise TopicIdentityMismatchError(
                "authenticated identity, topic, and event envelope must match"
            )

        received_at = self._clock()
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise ValueError("server clock must include a timezone offset")
        received_at = received_at.astimezone(UTC)
        if event.occurred_at > received_at + self._max_future_skew:
            raise TelemetryClockSkewError("event occurred_at exceeds allowed future skew")
        if event.sent_at > received_at + self._max_future_skew:
            raise TelemetryClockSkewError("event sent_at exceeds allowed future skew")
        if event.boot_started_at > received_at + self._max_future_skew:
            raise TelemetryClockSkewError("event boot_started_at exceeds allowed future skew")

        stored = StoredTelemetry(
            event=event,
            topic=topic,
            received_at=received_at,
            fingerprint=event.semantic_fingerprint(),
        )
        write = await self._repository.store(stored)

        return IngestionResult(
            accepted=write.created,
            duplicate=not write.created,
            latest_updated=write.latest_updated,
            telemetry=write.stored,
        )

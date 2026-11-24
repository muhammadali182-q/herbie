"""Application service for validated, idempotent telemetry ingestion."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from herbie.telemetry.contracts import TelemetryEvent
from herbie.telemetry.errors import TopicIdentityMismatchError
from herbie.telemetry.repository import StoredTelemetry, TelemetryArchive, TelemetryRepository
from herbie.telemetry.topic import TelemetryTopic


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
        archive: TelemetryArchive,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._archive = archive
        self._clock = clock or (lambda: datetime.now(UTC))

    async def ingest(self, topic: str, raw_payload: bytes | str) -> IngestionResult:
        topic_identity = TelemetryTopic.parse(topic)
        event = TelemetryEvent.from_json(raw_payload)
        if (
            event.tenant_id != topic_identity.tenant_id
            or event.charger_id != topic_identity.charger_id
        ):
            raise TopicIdentityMismatchError(
                "topic tenant and charger must match the event envelope"
            )

        stored = StoredTelemetry(event=event, received_at=self._clock())
        write = await self._repository.store(stored)
        # The archive port is idempotent so a retry can repair a prior archive
        # failure even when the hot-store write already succeeded.
        await self._archive.append(write.stored)

        return IngestionResult(
            accepted=write.created,
            duplicate=not write.created,
            latest_updated=write.latest_updated,
            telemetry=write.stored,
        )

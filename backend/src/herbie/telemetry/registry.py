"""Fleet-registry boundary used before trusting a broker-authorized route."""

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from herbie.telemetry.topic import DeviceIdentity, TelemetryTopic


class DeviceRegistry(Protocol):
    """Resolve only devices that are registered for telemetry ingestion."""

    async def resolve(self, topic: TelemetryTopic) -> DeviceIdentity | None:
        """Return a trusted identity when the route belongs to a known device."""


class StaticDeviceRegistry(DeviceRegistry):
    """Fail-closed configured registry for local and system-test profiles."""

    def __init__(self, identities: Iterable[DeviceIdentity]) -> None:
        self._identities = frozenset(
            (identity.tenant_id, identity.charger_id) for identity in identities
        )

    @classmethod
    def from_entries(cls, entries: Iterable[str]) -> "StaticDeviceRegistry":
        """Parse canonical ``tenant UUID/charger UUID`` configuration entries."""

        identities: list[DeviceIdentity] = []
        for entry in entries:
            parts = entry.split("/")
            if len(parts) != 2:
                raise ValueError("registered device must contain tenant and charger UUIDs")
            try:
                tenant_id = UUID(parts[0])
                charger_id = UUID(parts[1])
            except ValueError as error:
                raise ValueError("registered device identities must be UUIDs") from error
            if str(tenant_id) != parts[0] or str(charger_id) != parts[1]:
                raise ValueError("registered device identities must be canonical lowercase UUIDs")
            identities.append(DeviceIdentity(tenant_id=tenant_id, charger_id=charger_id))
        return cls(identities)

    async def resolve(self, topic: TelemetryTopic) -> DeviceIdentity | None:
        key = (topic.tenant_id, topic.charger_id)
        if key not in self._identities:
            return None
        return DeviceIdentity(tenant_id=topic.tenant_id, charger_id=topic.charger_id)

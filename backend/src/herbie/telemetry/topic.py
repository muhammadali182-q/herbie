"""Parsing and construction of trusted MQTT topic identities."""

from dataclasses import dataclass
from uuid import UUID

from herbie.telemetry.errors import InvalidTopicError


@dataclass(frozen=True, slots=True)
class TelemetryTopic:
    """Tenant and charger identity derived from an MQTT routing topic."""

    tenant_id: UUID
    charger_id: UUID

    @classmethod
    def parse(cls, topic: str) -> "TelemetryTopic":
        parts = topic.split("/")
        if (
            len(parts) != 8
            or parts[0:3] != ["herbie", "v1", "tenants"]
            or parts[4] != "chargers"
            or parts[6:8] != ["up", "telemetry"]
        ):
            raise InvalidTopicError("topic must match the v1 telemetry route")

        try:
            tenant_id = UUID(parts[3])
            charger_id = UUID(parts[5])
        except ValueError as error:
            raise InvalidTopicError("topic identities must be UUIDs") from error
        if str(tenant_id) != parts[3] or str(charger_id) != parts[5]:
            raise InvalidTopicError("topic identities must use canonical lowercase UUIDs")

        return cls(tenant_id=tenant_id, charger_id=charger_id)

    @classmethod
    def for_device(cls, tenant_id: UUID, charger_id: UUID) -> str:
        return f"herbie/v1/tenants/{tenant_id}/chargers/{charger_id}/up/telemetry"

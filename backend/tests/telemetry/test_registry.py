"""Device registry boundary tests."""

from uuid import UUID

import pytest

from herbie.telemetry.registry import StaticDeviceRegistry
from herbie.telemetry.topic import DeviceIdentity, TelemetryTopic

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
CHARGER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.mark.asyncio
async def test_static_registry_resolves_only_configured_devices() -> None:
    identity = DeviceIdentity(TENANT_ID, CHARGER_ID)
    registry = StaticDeviceRegistry([identity])

    assert await registry.resolve(TelemetryTopic(TENANT_ID, CHARGER_ID)) == identity
    assert await registry.resolve(TelemetryTopic(TENANT_ID, UUID(int=2))) is None


def test_static_registry_parses_canonical_configuration_entries() -> None:
    registry = StaticDeviceRegistry.from_entries([f"{TENANT_ID}/{CHARGER_ID}"])

    assert registry is not None


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ("missing-separator", "tenant and charger"),
        ("not-a-uuid/also-not", "must be UUIDs"),
        (f"{TENANT_ID}/{str(CHARGER_ID).upper()}", "canonical lowercase"),
    ],
)
def test_static_registry_rejects_invalid_configuration(entry: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        StaticDeviceRegistry.from_entries([entry])

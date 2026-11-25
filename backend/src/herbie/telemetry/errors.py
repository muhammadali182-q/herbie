"""Telemetry-domain errors with safe public messages."""


class TelemetryError(Exception):
    """Base class for expected telemetry ingestion failures."""


class InvalidTopicError(TelemetryError):
    """The MQTT topic does not follow the versioned upstream contract."""


class TopicIdentityMismatchError(TelemetryError):
    """The trusted topic identity differs from the payload identity."""


class MessageIdentityConflictError(TelemetryError):
    """A message ID was reused with different content."""


class SequenceIdentityConflictError(TelemetryError):
    """One boot sequence was reused with a different message identity."""


class BootIdentityConflictError(TelemetryError):
    """One boot ID was reused with a different boot start timestamp."""


class TelemetryClockSkewError(TelemetryError):
    """A device timestamp is implausibly ahead of server receipt time."""


class UnregisteredDeviceError(TelemetryError):
    """The broker-authorized route is not present in the fleet registry."""


class TelemetryPayloadTooLargeError(TelemetryError):
    """A telemetry payload exceeds the configured processing limit."""


class ArchiveObjectConflictError(TelemetryError):
    """An immutable archive object key was reused with other content."""

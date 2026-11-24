"""Telemetry-domain errors with safe public messages."""


class TelemetryError(Exception):
    """Base class for expected telemetry ingestion failures."""


class InvalidTopicError(TelemetryError):
    """The MQTT topic does not follow the versioned upstream contract."""


class TopicIdentityMismatchError(TelemetryError):
    """The trusted topic identity differs from the payload identity."""


class MessageIdentityConflictError(TelemetryError):
    """A message ID was reused with different content."""

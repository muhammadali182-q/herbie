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


class TelemetryClockSkewError(TelemetryError):
    """A device timestamp is implausibly ahead of server receipt time."""


class ArchiveObjectConflictError(TelemetryError):
    """An immutable archive object key was reused with other content."""

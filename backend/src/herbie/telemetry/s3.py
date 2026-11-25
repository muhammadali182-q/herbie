"""S3 immutable-object implementation of the canonical telemetry archive."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

from herbie.telemetry.archive import ArchiveBatch, TelemetryArchiveSink
from herbie.telemetry.errors import ArchiveObjectConflictError

CONDITIONAL_WRITE_RETRY_LIMIT = 3


class S3TelemetryArchiveSink(TelemetryArchiveSink):
    """Write deterministic gzip objects without overwriting other content."""

    def __init__(
        self,
        client: S3Client,
        bucket: str,
        kms_key_id: str | None = None,
        *,
        encrypt: bool = True,
    ) -> None:
        if kms_key_id and not encrypt:
            raise ValueError("KMS encryption cannot be disabled")
        self._client = client
        self._bucket = bucket
        self._kms_key_id = kms_key_id
        self._encrypt = encrypt

    async def put(self, batch: ArchiveBatch) -> None:
        await asyncio.to_thread(self._put, batch)

    def _put(self, batch: ArchiveBatch) -> None:
        request: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": batch.object_key,
            "Body": batch.content,
            "ContentEncoding": "gzip",
            "ContentType": "application/x-ndjson",
            "IfNoneMatch": "*",
            "Metadata": {
                "canonical-sha256": batch.checksum_sha256,
                "event-count": str(len(batch.events)),
                "archive-schema-version": "1.0",
            },
        }
        if self._kms_key_id:
            request["ServerSideEncryption"] = "aws:kms"
            request["SSEKMSKeyId"] = self._kms_key_id
        elif self._encrypt:
            request["ServerSideEncryption"] = "AES256"

        last_conflict: ClientError | None = None
        for _attempt in range(CONDITIONAL_WRITE_RETRY_LIMIT):
            try:
                self._client.put_object(**request)
                return
            except ClientError as error:
                status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                code = error.response.get("Error", {}).get("Code")
                precondition_failed = status == 412 or code == "PreconditionFailed"
                conditional_conflict = status == 409 or code == "ConditionalRequestConflict"
                if not precondition_failed and not conditional_conflict:
                    raise
                last_conflict = error
                existing, checksum = self._existing_checksum(batch.object_key)
                if existing:
                    if checksum != batch.checksum_sha256:
                        raise ArchiveObjectConflictError(
                            "archive key already contains different canonical content"
                        ) from error
                    return
                if precondition_failed:
                    raise

        if last_conflict is None:  # pragma: no cover - retry loop always executes
            raise RuntimeError("S3 conditional-write retry loop did not execute")
        raise last_conflict

    def _existing_checksum(self, object_key: str) -> tuple[bool, str | None]:
        try:
            existing = self._client.head_object(Bucket=self._bucket, Key=object_key)
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = error.response.get("Error", {}).get("Code")
            if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
                return False, None
            raise
        return True, existing.get("Metadata", {}).get("canonical-sha256")


def ensure_archive_bucket(
    client: S3Client,
    bucket: str,
    region: str,
    allow_unsupported_public_access_block: bool = False,
) -> None:
    """Create a local/demo archive bucket with public access blocked."""

    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as error:
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = error.response.get("Error", {}).get("Code")
        if status != 404 and code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        request: dict[str, Any] = {"Bucket": bucket}
        if region != "us-east-1":
            request["CreateBucketConfiguration"] = {"LocationConstraint": region}
        try:
            client.create_bucket(**request)
        except ClientError as create_error:
            code = create_error.response.get("Error", {}).get("Code")
            if code != "BucketAlreadyOwnedByYou":
                raise

    try:
        client.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        unsupported = code in {"MalformedXML", "NotImplemented", "XNotImplemented"}
        if not allow_unsupported_public_access_block or not unsupported:
            raise

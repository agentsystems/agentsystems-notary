"""Pluggable storage module for multi-cloud support.

This module provides a Storage protocol and implementations for various
cloud storage systems: AWS S3, GCP Cloud Storage, Azure Blob Storage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import boto3

if TYPE_CHECKING:
    from .config import (
        AwsS3StorageConfig,
        AzureBlobStorageConfig,
        GcpCloudStorageConfig,
        StorageConfig,
    )


class Storage(Protocol):
    """Protocol for cloud storage backends."""

    def put_object(
        self,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        """Write an object to storage."""
        ...

    @property
    def bucket_name(self) -> str:
        """Return the bucket/container name for logging."""
        ...


class AwsS3Storage:
    """AWS S3 storage implementation."""

    def __init__(self, config: AwsS3StorageConfig) -> None:
        self._config = config
        self._client: Any = boto3.client(
            "s3",
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            region_name=config.aws_region,
        )

    @property
    def bucket_name(self) -> str:
        """Return the S3 bucket name."""
        return self._config.bucket_name

    def put_object(
        self,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        """Write an object to S3."""
        self._client.put_object(
            Bucket=self._config.bucket_name,
            Key=key,
            Body=body,
            ContentType=content_type,
            Metadata=metadata,
        )


class GcpCloudStorage:
    """GCP Cloud Storage implementation.

    Status: Under development. Not yet available for use.
    """

    def __init__(self, config: GcpCloudStorageConfig) -> None:
        raise NotImplementedError(
            "GCP Cloud Storage is under development. "
            "Please use AwsS3StorageConfig for now."
        )

    @property
    def bucket_name(self) -> str:
        """Return the GCS bucket name."""
        raise NotImplementedError("GCP Cloud Storage is under development.")

    def put_object(
        self,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        """Write an object to GCS."""
        raise NotImplementedError("GCP Cloud Storage is under development.")


class AzureBlobStorage:
    """Azure Blob Storage implementation.

    Status: Under development. Not yet available for use.
    """

    def __init__(self, config: AzureBlobStorageConfig) -> None:
        raise NotImplementedError(
            "Azure Blob Storage is under development. "
            "Please use AwsS3StorageConfig for now."
        )

    @property
    def bucket_name(self) -> str:
        """Return the Azure container name."""
        raise NotImplementedError("Azure Blob Storage is under development.")

    def put_object(
        self,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        """Write an object to Azure Blob Storage."""
        raise NotImplementedError("Azure Blob Storage is under development.")


def create_storage(config: StorageConfig) -> Storage:
    """Factory function to create a Storage backend from configuration."""
    from .config import (
        AwsS3StorageConfig,
        AzureBlobStorageConfig,
        GcpCloudStorageConfig,
    )

    if isinstance(config, AwsS3StorageConfig):
        return AwsS3Storage(config)
    elif isinstance(config, GcpCloudStorageConfig):
        return GcpCloudStorage(config)
    elif isinstance(config, AzureBlobStorageConfig):
        return AzureBlobStorage(config)
    else:
        raise ValueError(f"Unknown storage config type: {type(config)}")

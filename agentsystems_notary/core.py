"""Framework-agnostic core logic for Notary compliance logging."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from typing import Any

import boto3
import httpx
import jcs

from .arweave import ArweaveBackend
from .config import ArweaveHashStorage, NotaryHashStorage, PayloadStorageConfig

try:
    __version__ = metadata.version("agentsystems-notary")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0"


# Maximum payload size for Arweave hash storage (10KB)
MAX_PAYLOAD_SIZE = 10 * 1024


class PayloadTooLargeError(Exception):
    """Raised when payload exceeds maximum size limit for Arweave hash storage."""

    pass


@dataclass
class LogResult:
    """Result from logging an interaction."""

    content_hash: str
    notary_receipt: str | None = None
    arweave_tx_id: str | None = None


# Type alias for hash storage options
HashStorage = NotaryHashStorage | ArweaveHashStorage


class NotaryCore:
    """
    Framework-agnostic notary logging core.

    Handles canonicalization, hashing, and storage for any AI framework.

    Args:
        payload_storage: Configuration for vendor's S3 bucket (full audit logs)
        hash_storage: List of hash storage configurations (Notary API and/or Arweave)
        debug: Enable debug output (default: False)

    Example:
        ```python
        from agentsystems_notary import (
            NotaryCore,
            PayloadStorageConfig,
            NotaryHashStorage,
        )

        payload_storage = PayloadStorageConfig(
            bucket_name="my-audit-logs",
            aws_access_key_id="...",
            aws_secret_access_key="...",
        )

        core = NotaryCore(
            payload_storage=payload_storage,
            hash_storage=[
                NotaryHashStorage(api_key="sk_asn_prod_...", slug="my_tenant"),
            ],
        )

        result = core.log_interaction(
            input_data={"prompt": "Hello"},
            output_data={"response": "Hi there!"},
        )
        print(f"Hash: {result.content_hash}")
        ```
    """

    def __init__(
        self,
        payload_storage: PayloadStorageConfig,
        hash_storage: list[HashStorage],
        debug: bool = False,
    ):
        if not hash_storage:
            raise ValueError("At least one hash_storage must be provided")

        self.payload_storage = payload_storage
        self.hash_storage = hash_storage
        self.debug = debug

        # Separate hash storage by type
        self._notary_storages = [
            h for h in hash_storage if isinstance(h, NotaryHashStorage)
        ]
        self._arweave_storages = [
            h for h in hash_storage if isinstance(h, ArweaveHashStorage)
        ]

        # Detect test mode from any Notary storage
        self.is_test_mode = any(
            h.api_key.startswith("sk_asn_test_") for h in self._notary_storages
        )

        # Initialize Arweave backends
        self._arweave_backends = [
            ArweaveBackend(storage, debug) for storage in self._arweave_storages
        ]

        # S3 client with explicit credentials
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=payload_storage.aws_access_key_id,
            aws_secret_access_key=payload_storage.aws_secret_access_key,
            region_name=payload_storage.aws_region,
        )

        # Session tracking
        self.session_id = str(uuid.uuid4())
        self.sequence = 0

    def log_interaction(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> LogResult:
        """
        Log an LLM interaction with cryptographic verification.

        This is the main entry point called by framework adapters.
        Performs: canonicalization -> hashing -> storage

        Args:
            input_data: Framework-specific input (prompts, messages, etc.)
            output_data: Framework-specific output (response text, etc.)
            metadata: Additional metadata to include

        Returns:
            LogResult with content hash and receipts/transaction IDs

        Raises:
            PayloadTooLargeError: If payload exceeds 10KB and Arweave is configured
            Exception: If any hash storage fails (strict mode)
        """
        self.sequence += 1

        # Build payload (include slug from first NotaryHashStorage if present)
        first_notary = self._notary_storages[0] if self._notary_storages else None
        payload = {
            "metadata": {
                "session_id": self.session_id,
                "sequence": self.sequence,
                "timestamp": datetime.now(UTC).isoformat(),
                "slug": first_notary.slug if first_notary else None,
                **(metadata or {}),
            },
            "input": input_data,
            "output": output_data,
        }

        # 1. Canonicalize (deterministic JSON serialization)
        canonical_bytes = jcs.canonicalize(payload)

        if self.debug:
            print("\n" + "=" * 80)
            print("DATA_TO_HASH (canonical JSON):")
            print(canonical_bytes.decode("utf-8"))
            print("=" * 80)

        # Check size limit (only if Arweave storage is configured)
        if self._arweave_storages and len(canonical_bytes) > MAX_PAYLOAD_SIZE:
            raise PayloadTooLargeError(
                f"Payload size ({len(canonical_bytes)} bytes) exceeds "
                f"maximum ({MAX_PAYLOAD_SIZE} bytes) for Arweave hash storage"
            )

        # 2. Hash
        content_hash = hashlib.sha256(canonical_bytes).hexdigest()

        if self.debug:
            print(f"HASH: {content_hash}")
            print("=" * 80 + "\n")

        # Initialize result
        result = LogResult(content_hash=content_hash)

        # 3. Write to hash storages (strict mode - any failure raises)
        # Each hash storage gets its own S3 path for clear separation
        for notary_storage in self._notary_storages:
            receipt, tenant_id = self._upload_to_notary(notary_storage, content_hash)
            result.notary_receipt = receipt  # Last one wins if multiple
            # Write full payload to S3 using tenant_id from API
            env = (
                "test" if notary_storage.api_key.startswith("sk_asn_test_") else "prod"
            )
            self._write_to_s3(canonical_bytes, content_hash, tenant_id, env)

        for i, arweave_backend in enumerate(self._arweave_backends):
            tx_id = arweave_backend.upload_hash(
                content_hash, self.session_id, self.sequence
            )
            result.arweave_tx_id = tx_id  # Last one wins if multiple
            # Write to S3 using namespace from Arweave storage
            namespace = self._arweave_storages[i].namespace
            self._write_to_s3(canonical_bytes, content_hash, namespace, "arweave")

        return result

    def _upload_to_notary(
        self,
        storage: NotaryHashStorage,
        content_hash: str,
    ) -> tuple[str, str]:
        """
        Upload hash to Notary API.

        Args:
            storage: NotaryHashStorage configuration
            content_hash: SHA-256 hash of canonical payload

        Returns:
            Tuple of (receipt, tenant_id)

        Raises:
            httpx.HTTPStatusError: If API request fails
            ValueError: If response missing tenant_id
        """
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                storage.api_url,
                headers={
                    "X-API-Key": storage.api_key,
                    "X-SDK-Version": __version__,
                },
                json={"hash": content_hash, "slug": storage.slug},
            )
            resp.raise_for_status()
            result = resp.json()
            receipt = result["receipt"]
            tenant_id = result.get("tenant_id")

        if not tenant_id:
            raise ValueError("Missing tenant_id from Notary API response")

        if self.debug:
            print(f"[Notary] Receipt: {receipt[:8]}...")

        return receipt, tenant_id

    def _write_to_s3(
        self,
        data_bytes: bytes,
        content_hash: str,
        path_prefix: str,
        env_prefix: str,
    ) -> None:
        """
        Write full payload to vendor's S3 bucket.

        Path: {env_prefix}/{path_prefix}/{YYYY}/{MM}/{DD}/{hash}.json

        Args:
            data_bytes: Canonical JSON bytes
            content_hash: SHA-256 hash (used in filename)
            path_prefix: tenant_id (Notary) or namespace (Arweave)
            env_prefix: "test", "prod", or "arweave"
        """
        date_path = datetime.now(UTC).strftime("%Y/%m/%d")
        key = f"{env_prefix}/{path_prefix}/{date_path}/{content_hash}.json"

        self.s3.put_object(
            Bucket=self.payload_storage.bucket_name,
            Key=key,
            Body=data_bytes,
            ContentType="application/json",
            Metadata={"hash": content_hash},
        )

        if self.debug:
            print(f"[S3] Saved: {self.payload_storage.bucket_name}/{key}")

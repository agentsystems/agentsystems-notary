"""Framework-agnostic core logic for Notary compliance logging."""

import hashlib
import uuid
import boto3
import jcs
import httpx
from datetime import datetime, timezone
from typing import Any, Dict


class NotaryCore:
    """
    Framework-agnostic notary logging core.

    Handles canonicalization, hashing, and dual-write for any AI framework.

    Args:
        api_key: Notary API key (from notary.agentsystems.ai)
        slug: Tenant slug (e.g., "tnt_acme_corp")
        vendor_bucket_name: S3 bucket name for raw logs
        api_url: Notary API endpoint (default: production)
        debug: Enable debug output (default: False)
    """

    def __init__(
        self,
        api_key: str,
        slug: str,
        vendor_bucket_name: str,
        api_url: str = "https://notary-api.agentsystems.ai/v1/notary",
        debug: bool = False
    ):
        self.api_key = api_key
        self.slug = slug
        self.bucket_name = vendor_bucket_name
        self.api_url = api_url
        self.debug = debug

        # Detect environment from API key prefix
        self.is_test_mode = api_key.startswith("sk_asn_test_")

        # Initialize S3 client (uses AWS credentials from environment)
        self.s3 = boto3.client("s3")

        # Session tracking
        self.session_id = str(uuid.uuid4())
        self.sequence = 0

        if self.debug and self.is_test_mode:
            print("[Notary] Running in TEST mode - logs will not be notarized")

    def log_interaction(
        self,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> None:
        """
        Log an LLM interaction with cryptographic verification.

        This is the main entry point called by framework adapters.
        Performs: canonicalization -> hashing -> dual-write

        Args:
            input_data: Framework-specific input (prompts, messages, etc.)
            output_data: Framework-specific output (response text, etc.)
            metadata: Additional metadata to include
        """
        self.sequence += 1

        # Build payload
        payload = {
            "metadata": {
                "session_id": self.session_id,
                "sequence": self.sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "slug": self.slug,
                **(metadata or {})
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

        # 2. Hash
        content_hash = hashlib.sha256(canonical_bytes).hexdigest()

        if self.debug:
            print(f"HASH: {content_hash}")
            print("=" * 80 + "\n")

        # 3. Dual-Write
        try:
            self._upload_and_notarize(canonical_bytes, content_hash, payload["metadata"])
        except Exception as e:
            print(f"Notary Log Failed: {e}")

    def _upload_and_notarize(
        self, data_bytes: bytes, content_hash: str, metadata: Dict[str, Any]
    ) -> None:
        """
        Perform dual-write to vendor S3 and Notary API.

        Args:
            data_bytes: Canonical JSON bytes to store in S3
            content_hash: SHA256 hash of canonical bytes
            metadata: Event metadata (session_id, slug, etc.)
        """
        # A. Vendor Storage (Customer's S3 Bucket)
        # Path: {env}/{slug}/{YYYY}/{MM}/{DD}/{hash}.json
        # where {env} is "prod" or "test" based on API key type
        env_prefix = "test" if self.is_test_mode else "prod"
        date_path = datetime.now(timezone.utc).strftime('%Y/%m/%d')
        key = f"{env_prefix}/{self.slug}/{date_path}/{content_hash}.json"

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data_bytes,
                ContentType="application/json",
                Metadata={"hash": content_hash},
            )
            if self.debug:
                print(f"[Vendor S3] Saved to {self.bucket_name}/{key}")
        except Exception as e:
            print(f"[Vendor S3] Failed: {e} (Check your AWS credentials)")
            return

        # B. Neutral Notary (AgentSystems API)
        # Always call API (handles tenant auto-creation, feed updates)
        # API will skip ledger write for test keys
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    self.api_url,
                    headers={"X-API-Key": self.api_key},
                    json={
                        "hash": content_hash,
                        "slug": self.slug,
                        "metadata": metadata,
                    },
                )
                if resp.status_code == 200:
                    receipt = resp.json()["receipt"]
                    if self.debug:
                        print(f"[Notary] Verified! Receipt: {receipt[:8]}...")
                else:
                    print(f"[Notary] Failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"[Notary] Connection Error: {e}")

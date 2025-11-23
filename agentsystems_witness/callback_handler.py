"""LangChain callback handler for Witness compliance logging."""

import hashlib
import uuid
import boto3
import jcs
import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler


class WitnessCallback(BaseCallbackHandler):
    """
    LangChain callback handler that logs LLM interactions for compliance.

    Performs dual-write:
    1. Vendor's S3 bucket (raw canonical JSON)
    2. Witness API (cryptographic hash receipt)

    Args:
        api_key: Witness API key (from witness.agentsystems.ai)
        tenant_id: Tenant identifier (e.g., "tnt_acme_corp")
        vendor_bucket_name: S3 bucket name for raw logs
        api_url: Witness API endpoint (default: production)
        debug: Enable debug output (default: False)

    Example:
        ```python
        from agentsystems_witness import WitnessCallback
        from langchain_anthropic import ChatAnthropic

        callback = WitnessCallback(
            api_key="sk_live_...",
            tenant_id="tnt_acme_corp",
            vendor_bucket_name="acme-llm-logs"
        )

        model = ChatAnthropic(
            model="claude-sonnet-4",
            callbacks=[callback]
        )

        response = model.invoke("What is AIUC-1 compliance?")
        ```
    """

    def __init__(
        self,
        api_key: str,
        tenant_id: str,
        vendor_bucket_name: str,
        api_url: str = "https://witness-api.agentsystems.ai/v1/witness",
        debug: bool = False
    ):
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.bucket_name = vendor_bucket_name
        self.api_url = api_url
        self.debug = debug

        # Initialize S3 client (uses AWS credentials from environment)
        self.s3 = boto3.client("s3")

        # Session tracking
        self.session_id = str(uuid.uuid4())
        self.sequence = 0
        self.current_request: Dict[str, Any] = {}

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Capture LLM request metadata."""
        self.sequence += 1
        self.current_request = {
            "prompts": prompts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_config": kwargs.get("invocation_params", {}),
        }

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Capture LLM response and perform dual-write."""
        response_text = response.generations[0][0].text if response.generations else ""

        # Build payload
        payload = {
            "metadata": {
                "session_id": self.session_id,
                "sequence": self.sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tenant_id": self.tenant_id,
                "vendor_id": "inferred_from_api_key",
            },
            "input": self.current_request,
            "output": {"text": response_text},
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
            self._upload_and_witness(canonical_bytes, content_hash, payload["metadata"])
        except Exception as e:
            print(f"❌ Compliance Log Failed: {e}")

    def _upload_and_witness(
        self, data_bytes: bytes, content_hash: str, metadata: Dict[str, Any]
    ) -> None:
        """
        Perform dual-write to vendor S3 and Witness API.

        Args:
            data_bytes: Canonical JSON bytes to store in S3
            content_hash: SHA256 hash of canonical bytes
            metadata: Event metadata (session_id, tenant_id, etc.)
        """
        # A. Vendor Storage (Customer's S3 Bucket)
        key = f"logs/{self.tenant_id}/{self.session_id}/{self.sequence}.json"

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data_bytes,
                ContentType="application/json",
                Metadata={"hash": content_hash},
            )
            if self.debug:
                print(f"✅ [Vendor S3] Saved to {self.bucket_name}/{key}")
        except Exception as e:
            print(f"❌ [Vendor S3] Failed: {e} (Check your AWS credentials)")
            return

        # B. Neutral Witness (AgentSystems API)
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    self.api_url,
                    headers={"X-API-Key": self.api_key},
                    json={
                        "hash": content_hash,
                        "tenant_id": self.tenant_id,
                        "metadata": metadata,
                    },
                )
                if resp.status_code == 200:
                    receipt = resp.json()["receipt"]
                    if self.debug:
                        print(f"✅ [Witness] Verified! Receipt: {receipt[:8]}...")
                else:
                    print(f"❌ [Witness] Failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"❌ [Witness] Connection Error: {e}")

"""LangChain adapter for Notary compliance logging."""

from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from .config import RawPayloadStorage
from .core import HashStorage, NotaryCore


class LangChainNotary(BaseCallbackHandler):  # type: ignore[misc]
    """
    LangChain callback handler for Notary logging.

    This is a thin adapter that extracts data from LangChain's callback
    interface and passes it to the framework-agnostic NotaryCore.

    Args:
        raw_payload_storage: Configuration for vendor's S3 bucket (full audit logs)
        hash_storage: List of hash storage configurations (custodied and/or Arweave)
        debug: Enable debug output (default: False)

    Example:
        ```python
        from agentsystems_notary import (
            LangChainNotary,
            RawPayloadStorage,
            CustodiedHashStorage,
        )
        from langchain_anthropic import ChatAnthropic

        raw_payload_storage = RawPayloadStorage(
            bucket_name="acme-corp-audit-logs",
            aws_access_key_id="...",
            aws_secret_access_key="...",
        )

        callback = LangChainNotary(
            raw_payload_storage=raw_payload_storage,
            hash_storage=[
                CustodiedHashStorage(
                    api_key="sk_asn_prod_...",
                    slug="tnt_acme_corp",
                ),
            ],
        )

        model = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            callbacks=[callback]
        )

        response = model.invoke("What is AIUC-1 compliance?")
        ```
    """

    def __init__(
        self,
        raw_payload_storage: RawPayloadStorage,
        hash_storage: list[HashStorage],
        debug: bool = False,
    ):
        # Initialize framework-agnostic core
        self.core = NotaryCore(
            raw_payload_storage=raw_payload_storage,
            hash_storage=hash_storage,
            debug=debug,
        )

        # Pending requests keyed by run_id for concurrent call isolation
        self._pending_requests: dict[UUID, dict[str, Any]] = {}

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Capture LLM request metadata."""
        self._pending_requests[run_id] = {
            "prompts": prompts,
            "timestamp": kwargs.get("timestamp"),
            "model_config": kwargs.get("invocation_params", {}),
        }

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        """
        Capture LLM response and log to Notary.

        Extracts response from LangChain's response object and calls
        the framework-agnostic core logging method.
        """
        request_data = self._pending_requests.pop(run_id, None)
        if request_data is None:
            return

        # Extract response text from LangChain's response structure
        if response.generations:
            response_text = response.generations[0][0].text
        else:
            response_text = ""

        # Call framework-agnostic core
        self.core.log_interaction(
            input_data=request_data,
            output_data={"text": response_text},
            metadata={},
        )

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        """Clean up pending request on LLM error to prevent memory leaks."""
        self._pending_requests.pop(run_id, None)

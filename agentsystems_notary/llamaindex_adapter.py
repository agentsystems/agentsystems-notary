"""LlamaIndex adapter for Notary compliance logging."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import RawPayloadStorage
from .core import HashStorage, NotaryCore

# Type checking imports
if TYPE_CHECKING:
    from llama_index.core.instrumentation.events.llm import (
        LLMChatEndEvent,
        LLMChatStartEvent,
    )

# Runtime imports
try:
    from llama_index.core.instrumentation import get_dispatcher
    from llama_index.core.instrumentation.event_handlers import BaseEventHandler
    from llama_index.core.instrumentation.events.llm import (
        LLMChatEndEvent as _LLMChatEndEvent,
    )
    from llama_index.core.instrumentation.events.llm import (
        LLMChatStartEvent as _LLMChatStartEvent,
    )

    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False
    BaseEventHandler = object
    _LLMChatStartEvent = None
    _LLMChatEndEvent = None

    def get_dispatcher() -> Any:
        raise ImportError("LlamaIndex is not installed")


class LlamaIndexNotary(BaseEventHandler):  # type: ignore[misc]
    """
    LlamaIndex event handler for Notary compliance logging.

    This is a thin adapter that extracts data from LlamaIndex's instrumentation
    events and passes it to the framework-agnostic NotaryCore.

    Args:
        raw_payload_storage: Configuration for vendor's S3 bucket (full audit logs)
        hash_storage: List of hash storage configurations (custodied and/or Arweave)
        debug: Enable debug output (default: False)
        auto_register: Automatically register with root dispatcher (default: True)

    Example:
        ```python
        from agentsystems_notary import (
            LlamaIndexNotary,
            RawPayloadStorage,
            CustodiedHashStorage,
        )
        from llama_index.llms.anthropic import Anthropic

        raw_payload_storage = RawPayloadStorage(
            storage=AwsS3StorageConfig(
                bucket_name="acme-corp-audit-logs",
                aws_access_key_id="...",
                aws_secret_access_key="...",
            )
        )

        # Initialize notary - automatically registers with LlamaIndex
        notary = LlamaIndexNotary(
            raw_payload_storage=raw_payload_storage,
            hash_storage=[
                CustodiedHashStorage(
                    api_key="sk_asn_prod_...",
                    slug="tnt_acme_corp",
                ),
            ],
        )

        # All LLM calls are logged automatically
        llm = Anthropic(model="claude-sonnet-4-5-20250929")
        response = llm.chat(messages)
        ```
    """

    # Pydantic fields - NotaryCore must be Any to avoid validation issues
    core: Any = None
    _pending_requests: dict[str, dict[str, Any]] = {}
    _pre_execution_record: dict[str, Any] | None = None

    def __init__(
        self,
        raw_payload_storage: RawPayloadStorage,
        hash_storage: list[HashStorage],
        debug: bool = False,
        auto_register: bool = True,
        pre_execution_record: dict[str, Any] | None = None,
    ):
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not installed. "
                "Install it with: pip install llama-index-core"
            )

        # Initialize Pydantic BaseModel with core field
        super().__init__(
            core=NotaryCore(
                raw_payload_storage=raw_payload_storage,
                hash_storage=hash_storage,
                debug=debug,
            ),
            _pending_requests={},
            _pre_execution_record=pre_execution_record,
        )

        # Register with LlamaIndex dispatcher
        if auto_register:
            self._register()

    def _register(self) -> None:
        """Register this handler with the root LlamaIndex dispatcher."""
        dispatcher = get_dispatcher()
        dispatcher.add_event_handler(self)

    @classmethod
    def class_name(cls) -> str:
        """Return class name for LlamaIndex instrumentation."""
        return "LlamaIndexNotary"

    def handle(self, event: Any) -> None:
        """
        Handle LlamaIndex instrumentation events.

        Captures LLM chat start and end events to log interactions.
        """
        if _LLMChatStartEvent is not None and isinstance(event, _LLMChatStartEvent):
            self._handle_start(event)
        elif _LLMChatEndEvent is not None and isinstance(event, _LLMChatEndEvent):
            self._handle_end(event)

    def _handle_start(self, event: LLMChatStartEvent) -> None:
        """Capture LLM request metadata from start event."""
        # Extract messages from the event
        messages = []
        if hasattr(event, "messages") and event.messages:
            for msg in event.messages:
                messages.append(
                    {
                        "role": getattr(msg, "role", "unknown"),
                        "content": getattr(
                            msg, "content", getattr(msg, "text", str(msg))
                        ),
                    }
                )

        # Extract model configuration
        model_config = {}
        if hasattr(event, "model_dict") and event.model_dict:
            model_config = event.model_dict
        elif hasattr(event, "additional_kwargs"):
            model_config = event.additional_kwargs

        # Store request data keyed by span_id
        self._pending_requests[event.span_id] = {
            "messages": messages,
            "model_config": model_config,
        }

    def _handle_end(self, event: LLMChatEndEvent) -> None:
        """Capture LLM response and log to Notary."""
        request_data = self._pending_requests.pop(event.span_id, None)
        if request_data is None:
            return

        # Extract response text from the event
        response_text = ""
        if hasattr(event, "response") and event.response:
            response = event.response
            if hasattr(response, "message"):
                # ChatResponse structure
                message = response.message
                response_text = getattr(
                    message, "content", getattr(message, "text", str(message))
                )
            elif hasattr(response, "text"):
                response_text = response.text
            else:
                response_text = str(response)

        # Extract metadata
        metadata: dict[str, Any] = {}
        if hasattr(event, "response") and event.response:
            if hasattr(event.response, "raw"):
                metadata["raw_response_type"] = type(event.response.raw).__name__

        # Call framework-agnostic core
        self.core.log_interaction(
            input_data=request_data,
            output_data={"text": response_text},
            metadata=metadata,
            pre_execution_record=self._pre_execution_record,
        )

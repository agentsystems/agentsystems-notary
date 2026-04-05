"""Agno adapter for Notary compliance logging."""

import threading
from collections.abc import Callable
from typing import Any

from .config import RawPayloadStorage
from .core import HashStorage, NotaryCore

try:
    from agno.agent import Agent  # noqa: F401

    AGNO_AVAILABLE = True
except ImportError:
    AGNO_AVAILABLE = False


class AgnoNotary:
    """
    Agno hook handler for Notary compliance logging.

    This is a thin adapter that extracts data from Agno's hook context
    and passes it to the framework-agnostic NotaryCore.

    Args:
        raw_payload_storage: Configuration for vendor's S3 bucket (full audit logs)
        hash_storage: List of hash storage configurations (custodied and/or Arweave)
        debug: Enable debug output (default: False)

    Example:
        ```python
        from agentsystems_notary import (
            AgnoNotary,
            RawPayloadStorage,
            CustodiedHashStorage,
        )
        from agno.agent import Agent
        from agno.models.anthropic import Claude

        raw_payload_storage = RawPayloadStorage(
            storage=AwsS3StorageConfig(
                bucket_name="acme-corp-audit-logs",
                aws_access_key_id="...",
                aws_secret_access_key="...",
            )
        )

        # Initialize notary
        notary = AgnoNotary(
            raw_payload_storage=raw_payload_storage,
            hash_storage=[
                CustodiedHashStorage(
                    api_key="sk_asn_prod_...",
                    slug="tnt_acme_corp",
                ),
            ],
        )

        # Create agent with notary hooks
        agent = Agent(
            model=Claude(id="claude-sonnet-4-5-20250929"),
            instructions="You are a helpful assistant.",
            **notary.get_hooks(),
        )

        # All LLM calls are logged automatically
        agent.print_response("What is AIUC-1 compliance?")
        ```
    """

    def __init__(
        self,
        raw_payload_storage: RawPayloadStorage,
        hash_storage: list[HashStorage],
        debug: bool = False,
        pre_execution_record: dict[str, Any] | None = None,
    ):
        if not AGNO_AVAILABLE:
            raise ImportError(
                "Agno is not installed. Install it with: pip install agno"
            )

        # Initialize framework-agnostic core
        self.core = NotaryCore(
            raw_payload_storage=raw_payload_storage,
            hash_storage=hash_storage,
            debug=debug,
        )

        self._pre_execution_record = pre_execution_record

        # Temporary storage for request data
        # Using a dict keyed by id to handle potential concurrent calls
        self._pending_requests: dict[int, dict[str, Any]] = {}
        self._request_counter = 0
        self._counter_lock = threading.Lock()

    def _pre_hook(
        self,
        run_input: Any = None,
        run_context: Any = None,
        agent: Any = None,
        session: Any = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Capture agent request from Agno run_input.

        Called right after agent-session is loaded, before processing starts.

        Args:
            run_input: RunInput with input_content, images, videos, etc.
            run_context: RunContext with run metadata
            agent: The Agno Agent instance
            session: AgentSession with session state
            user_id: Optional user ID
        """
        # Extract input content from run_input
        input_content = ""
        if run_input is not None:
            if hasattr(run_input, "input_content"):
                content = run_input.input_content
                if isinstance(content, str):
                    input_content = content
                elif hasattr(content, "content"):
                    input_content = content.content
                else:
                    input_content = str(content)

        # Extract agent metadata
        agent_info: dict[str, Any] = {}
        if agent is not None:
            if hasattr(agent, "name") and agent.name:
                agent_info["name"] = agent.name
            if hasattr(agent, "model") and agent.model:
                model = agent.model
                if hasattr(model, "id"):
                    agent_info["model_id"] = model.id
                elif hasattr(model, "model"):
                    agent_info["model_id"] = model.model
            if hasattr(agent, "instructions") and agent.instructions:
                instructions = agent.instructions
                if isinstance(instructions, str) and len(instructions) > 200:
                    instructions = instructions[:200] + "..."
                agent_info["instructions"] = instructions

        # Store request data keyed by run_context for retrieval in post_hook
        with self._counter_lock:
            self._request_counter += 1
            request_id = self._request_counter
        self._pending_requests[request_id] = {
            "input": input_content,
            "agent": agent_info,
        }

        # Attach request_id to run_context for retrieval in post_hook
        if run_context is not None and hasattr(run_context, "__dict__"):
            run_context._notary_request_id = request_id

    def _post_hook(
        self,
        run_output: Any = None,
        run_context: Any = None,
        agent: Any = None,
        session: Any = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Capture agent response and log to Notary.

        Called after output is generated but before the response is returned.

        Args:
            run_output: RunOutput with content, messages, metrics, etc.
            run_context: RunContext with run metadata
            agent: The Agno Agent instance
            session: AgentSession with session state
            user_id: Optional user ID
        """
        # Retrieve request_id from run_context
        request_id = getattr(run_context, "_notary_request_id", None)
        if request_id is None:
            return

        request_data = self._pending_requests.pop(request_id, None)
        if request_data is None:
            return

        # Extract response from run_output
        response_text = ""
        if run_output is not None:
            if hasattr(run_output, "content") and run_output.content:
                content = run_output.content
                if isinstance(content, str):
                    response_text = content
                else:
                    response_text = str(content)

        # Build metadata
        metadata: dict[str, Any] = {}
        if run_output is not None:
            if hasattr(run_output, "run_id") and run_output.run_id:
                metadata["run_id"] = str(run_output.run_id)
            if hasattr(run_output, "session_id") and run_output.session_id:
                metadata["session_id"] = str(run_output.session_id)
            if hasattr(run_output, "model") and run_output.model:
                metadata["model"] = run_output.model

        # Call framework-agnostic core
        self.core.log_interaction(
            input_data=request_data,
            output_data={"text": response_text},
            metadata=metadata,
            pre_execution_record=self._pre_execution_record,
        )

    def get_hooks(self) -> dict[str, list[Callable[..., Any]]]:
        """
        Return hooks dictionary for passing to Agno Agent constructor.

        Returns:
            Dictionary with pre_hooks and post_hooks lists.

        Example:
            ```python
            notary = AgnoNotary(...)
            agent = Agent(model=..., **notary.get_hooks())
            ```
        """
        return {
            "pre_hooks": [self._pre_hook],
            "post_hooks": [self._post_hook],
        }

    @property
    def pre_hook(self) -> Callable[..., Any]:
        """Return the pre-hook function for manual registration."""
        return self._pre_hook

    @property
    def post_hook(self) -> Callable[..., Any]:
        """Return the post-hook function for manual registration."""
        return self._post_hook

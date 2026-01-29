"""CrewAI adapter for Notary compliance logging."""

from typing import Any

from .config import PayloadStorageConfig
from .core import HashStorage, NotaryCore

try:
    from crewai.hooks import after_llm_call, before_llm_call

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


class CrewAINotary:
    """
    CrewAI hook handler for Notary compliance logging.

    This is a thin adapter that extracts data from CrewAI's hook context
    and passes it to the framework-agnostic NotaryCore.

    Args:
        payload_storage: Configuration for vendor's S3 bucket (full audit logs)
        hash_storage: List of hash storage configurations (Notary API and/or Arweave)
        debug: Enable debug output (default: False)

    Example:
        ```python
        from agentsystems_notary import (
            CrewAINotary,
            PayloadStorageConfig,
            NotaryHashStorage,
        )
        from crewai import Agent, Task, Crew

        payload_storage = PayloadStorageConfig(
            bucket_name="acme-corp-audit-logs",
            aws_access_key_id="...",
            aws_secret_access_key="...",
        )

        # Initialize notary logging
        notary = CrewAINotary(
            payload_storage=payload_storage,
            hash_storage=[
                NotaryHashStorage(
                    api_key="sk_asn_prod_...",
                    slug="tnt_acme_corp",
                ),
            ],
        )

        # Create crew - hooks are automatically registered
        agent = Agent(role="Research Analyst", ...)
        task = Task(description="Research AIUC-1 compliance", ...)
        crew = Crew(agents=[agent], tasks=[task])

        # All LLM calls are logged automatically
        crew.kickoff()
        ```
    """

    def __init__(
        self,
        payload_storage: PayloadStorageConfig,
        hash_storage: list[HashStorage],
        debug: bool = False,
    ):
        if not CREWAI_AVAILABLE:
            raise ImportError(
                "CrewAI is not installed. Install it with: pip install crewai"
            )

        # Initialize framework-agnostic core
        self.core = NotaryCore(
            payload_storage=payload_storage,
            hash_storage=hash_storage,
            debug=debug,
        )

        # Temporary storage for request data
        self._current_request: dict[str, Any] | None = None

        # Register hooks with CrewAI
        self._register_hooks()

    def _register_hooks(self) -> None:
        """Register before/after hooks with CrewAI."""

        @before_llm_call  # type: ignore
        def _notary_before_llm(context: Any) -> None:
            """Capture LLM request from CrewAI context."""
            # Extract messages from context
            messages = []
            if hasattr(context, "messages") and context.messages:
                for msg in context.messages:
                    messages.append(
                        {
                            "role": getattr(msg, "role", "unknown"),
                            "content": getattr(msg, "content", str(msg)),
                        }
                    )

            # Store request data
            self._current_request = {
                "messages": messages,
                "agent": context.agent.role if context.agent else None,
                "task": context.task.description if context.task else None,
                "crew": context.crew.name if hasattr(context.crew, "name") else None,
            }

            return None  # Allow execution

        @after_llm_call  # type: ignore
        def _notary_after_llm(context: Any) -> None:
            """Capture LLM response and log to Notary."""
            if self._current_request is None:
                return None

            # Extract response from context
            output_data = {
                "text": context.response if hasattr(context, "response") else ""
            }

            # Build metadata from CrewAI context
            metadata: dict[str, Any] = {}
            if context.agent:
                metadata["agent_role"] = context.agent.role
            if context.task:
                # Truncate long descriptions
                metadata["task_description"] = context.task.description[:100]
            if hasattr(context, "iterations"):
                metadata["iteration"] = context.iterations

            # Call framework-agnostic core
            self.core.log_interaction(
                input_data=self._current_request,
                output_data=output_data,
                metadata=metadata,
            )

            return None  # Don't modify response

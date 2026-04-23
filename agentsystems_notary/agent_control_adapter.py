"""Agent Control adapter for Notary compliance logging.

Exposes `AgentControlNotarySink`, a `BaseControlEventSink` implementation that
forwards every Agent Control `ControlExecutionEvent` into a `NotaryCore`
instance. Register it once with `register_control_event_sink(...)` and
every control evaluation across every agent is notarized automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .core import NotaryCore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from agent_control_models import ControlExecutionEvent

try:
    from agent_control.observability import BaseControlEventSink, SinkResult

    AGENT_CONTROL_AVAILABLE = True
except ImportError:
    AGENT_CONTROL_AVAILABLE = False
    BaseControlEventSink = object
    SinkResult = None


class AgentControlNotarySink(BaseControlEventSink):  # type: ignore[misc]
    """
    Agent Control event sink that notarizes every control execution event.

    Forwards each `ControlExecutionEvent` through `NotaryCore.log_interaction()`,
    producing a canonical JSON record (hashed with SHA-256) for every control
    evaluation — whether the control matched or not. Register the sink once at
    startup and every agent governed by Agent Control is captured automatically.

    Args:
        core: A configured `NotaryCore` instance that handles hashing and storage.

    Example:
        ```python
        from agent_control.observability import register_control_event_sink
        from agentsystems_notary import (
            ArweaveHashStorage,
            AwsS3StorageConfig,
            LocalKeySignerConfig,
            NotaryCore,
            AgentControlNotarySink,
            RawPayloadStorage,
        )

        notary = NotaryCore(
            raw_payload_storage=RawPayloadStorage(
                storage=AwsS3StorageConfig(
                    bucket_name="my-audit-logs",
                    aws_access_key_id="...",
                    aws_secret_access_key="...",
                ),
            ),
            hash_storage=[
                ArweaveHashStorage(
                    namespace="my-agent-namespace",
                    signer=LocalKeySignerConfig(
                        private_key_path="./arweave-key.pem"
                    ),
                )
            ],
        )

        register_control_event_sink(AgentControlNotarySink(notary))
        ```
    """

    def __init__(self, core: NotaryCore):
        if not AGENT_CONTROL_AVAILABLE:
            raise ImportError(
                "Agent Control is not installed. "
                "Install it with: pip install agent-control-sdk"
            )
        self.core = core

    def write_events(
        self, events: Sequence[ControlExecutionEvent]
    ) -> Any:  # SinkResult — typed Any to avoid import at module load
        """
        Forward each control event to `NotaryCore.log_interaction()`.

        Per-event errors are caught and counted as dropped so a single
        failure never aborts the batch.
        """
        accepted = 0
        dropped = 0
        for event in events:
            try:
                self.core.log_interaction(
                    input_data={
                        "selector_path": event.selector_path,
                        "check_stage": event.check_stage,
                    },
                    output_data={
                        "matched": event.matched,
                        "action": event.action,
                    },
                    pre_execution_record=event.model_dump(mode="json"),
                )
                accepted += 1
            except Exception:
                dropped += 1
        return SinkResult(accepted=accepted, dropped=dropped)

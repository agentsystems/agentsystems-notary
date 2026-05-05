"""Faramesh adapter for Notary compliance logging.

Exposes ``FarameshNotarySink``, a callable that consumes events from
Faramesh's two SDK socket streams — ``faramesh.audit`` (every
governance decision) and ``faramesh.callbacks`` (lifecycle events
including deferred-decision resolutions) — and forwards each one
through ``NotaryCore.log_interaction()``. Subscribe once per stream
and every decision *and* its eventual resolution is automatically
notarized.
"""

from __future__ import annotations

import logging
from typing import Any

from .core import NotaryCore

logger = logging.getLogger("agentsystems_notary.faramesh")

try:
    # Presence check for both submodules used by callers of this adapter.
    import faramesh.audit  # noqa: F401
    import faramesh.callbacks  # noqa: F401

    FARAMESH_AVAILABLE = True
except ImportError:
    FARAMESH_AVAILABLE = False


class FarameshNotarySink:
    """Callable that notarizes Faramesh decisions and their resolutions.

    Subscribe one instance to each of Faramesh's two streams to capture
    the full lifecycle:

    ```python
    from faramesh import audit, callbacks
    from agentsystems_notary import (
        ArweaveHashStorage,
        AwsS3StorageConfig,
        FarameshNotarySink,
        LocalKeySignerConfig,
        NotaryCore,
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
                signer=LocalKeySignerConfig(private_key_path="./arweave-key.pem"),
            )
        ],
    )

    sink = FarameshNotarySink(notary)
    decisions_sub = audit.subscribe(sink)      # PERMIT / DENY / DEFER
    resolutions_sub = callbacks.subscribe(sink)  # defer_resolved, etc.
    # ... run agents; both decisions and resolutions are notarized ...
    decisions_sub.close()
    resolutions_sub.close()
    ```

    The sink branches on ``event.get("event_type")``:

    * **Decision events** (no ``event_type``) come from ``faramesh.audit``.
      ``input_data`` carries ``tool_id`` / ``operation`` / ``args``;
      ``output_data`` carries ``effect`` / ``reason_code`` / ``latency_ms``.
    * **Lifecycle events with** ``event_type == "decision"`` are skipped:
      the daemon mirrors every decision onto the callbacks stream in
      addition to the audit stream, so notarizing it would double-record
      the same decision. The audit-stream copy wins.
    * **Other lifecycle events** (``event_type == "defer_resolved"``,
      ``"defer_expired"``, etc.) come from ``faramesh.callbacks``.
      ``input_data`` carries ``event_type`` / ``defer_token``;
      ``output_data`` carries ``status`` / ``approved`` / ``approver_id``
      / ``reason``. The ``defer_token`` is the linkage back to the
      original DEFER record.

    In all notarized cases the full raw event is preserved as
    ``pre_execution_record``.

    Backpressure note: Faramesh's daemon buffers ~64 events per
    subscriber and silently drops further events if the consumer
    lags. ``NotaryCore.log_interaction()`` includes an Arweave (or
    custodied) upload that can take hundreds of milliseconds. At
    sustained throughput this can cause event loss. If that's a
    concern, wrap the sink in your own ``queue.Queue`` and process
    notarizations on a worker thread.

    Concurrency note: if you're doing heavy synchronous work
    (Arweave uploads, large S3 PUTs) on one stream, run the other
    stream in a separate process. Mixing both streams + heavy sync
    I/O in one Python process has shown event loss on the lifecycle
    stream.

    Args:
        core: A configured ``NotaryCore`` that handles hashing and storage.
    """

    def __init__(self, core: NotaryCore):
        if not FARAMESH_AVAILABLE:
            raise ImportError(
                "faramesh-sdk with the audit and callbacks modules is required. "
                "Install with: pip install 'agentsystems-notary[faramesh]' "
                "(or pip install 'faramesh-sdk>=0.4.0' directly)."
            )
        self.core = core

    def __call__(self, event: dict[str, Any]) -> None:
        """Notarize a single Faramesh event (decision or lifecycle).

        Skips ``event_type == "decision"`` events: the daemon mirrors every
        decision onto the callbacks stream as a ``decision`` event in
        addition to broadcasting it on the audit stream. When the sink
        is wired to both streams (the recommended setup), that mirror is
        a duplicate of the audit-stream event and would notarize the
        same decision twice.

        Errors are logged and swallowed so a transient failure does not
        kill the subscription thread.
        """
        event_type = event.get("event_type")
        if event_type == "decision":
            # Duplicate of the audit_subscribe stream; skip to avoid
            # double-notarization.
            return
        try:
            if event_type:
                input_data, output_data = self._map_lifecycle_event(event)
            else:
                input_data, output_data = self._map_decision_event(event)
            self.core.log_interaction(
                input_data=input_data,
                output_data=output_data,
                pre_execution_record=event,
            )
        except Exception:
            logger.exception("Failed to notarize Faramesh audit event")

    @staticmethod
    def _map_decision_event(
        event: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return (
            {
                "tool_id": event.get("tool_id"),
                "operation": event.get("operation"),
                "args": event.get("args"),
            },
            {
                "effect": event.get("effect"),
                "reason_code": event.get("reason_code"),
                "latency_ms": event.get("latency_ms"),
            },
        )

    @staticmethod
    def _map_lifecycle_event(
        event: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return (
            {
                "event_type": event.get("event_type"),
                "defer_token": event.get("defer_token"),
            },
            {
                "status": event.get("status"),
                "approved": event.get("approved"),
                "approver_id": event.get("approver_id"),
                "reason": event.get("reason"),
            },
        )

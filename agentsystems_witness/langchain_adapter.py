"""LangChain adapter for Witness compliance logging."""

from typing import Any, Dict, List
from langchain_core.callbacks import BaseCallbackHandler
from .core import WitnessCore


class LangChainWitness(BaseCallbackHandler):
    """
    LangChain callback handler for Witness compliance logging.

    This is a thin adapter that extracts data from LangChain's callback
    interface and passes it to the framework-agnostic WitnessCore.

    Args:
        api_key: Witness API key (from witness.agentsystems.ai)
        tenant_id: Tenant identifier (e.g., "tnt_acme_corp")
        vendor_bucket_name: S3 bucket name for raw logs
        api_url: Witness API endpoint (default: production)
        debug: Enable debug output (default: False)

    Example:
        ```python
        from agentsystems_witness import LangChainWitness
        from langchain_anthropic import ChatAnthropic

        callback = LangChainWitness(
            api_key="sk_live_...",
            tenant_id="tnt_acme_corp",
            vendor_bucket_name="acme-llm-logs"
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
        api_key: str,
        tenant_id: str,
        vendor_bucket_name: str,
        api_url: str = "https://witness-api.agentsystems.ai/v1/witness",
        debug: bool = False
    ):
        # Initialize framework-agnostic core
        self.core = WitnessCore(
            api_key=api_key,
            tenant_id=tenant_id,
            vendor_bucket_name=vendor_bucket_name,
            api_url=api_url,
            debug=debug
        )

        # Temporary storage for request data
        self.current_request: Dict[str, Any] = {}

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Capture LLM request metadata."""
        self.current_request = {
            "prompts": prompts,
            "timestamp": kwargs.get("timestamp"),
            "model_config": kwargs.get("invocation_params", {}),
        }

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """
        Capture LLM response and log to Witness.

        Extracts response from LangChain's response object and calls
        the framework-agnostic core logging method.
        """
        # Extract response text from LangChain's response structure
        response_text = response.generations[0][0].text if response.generations else ""

        # Call framework-agnostic core
        self.core.log_interaction(
            input_data=self.current_request,
            output_data={"text": response_text},
            metadata={}
        )

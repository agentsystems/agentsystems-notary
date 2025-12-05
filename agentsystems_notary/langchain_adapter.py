"""LangChain adapter for Notary compliance logging."""

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from .core import NotaryCore


class LangChainNotary(BaseCallbackHandler):  # type: ignore[misc]
    """
    LangChain callback handler for Notary compliance logging.

    This is a thin adapter that extracts data from LangChain's callback
    interface and passes it to the framework-agnostic NotaryCore.

    Args:
        api_key: Notary API key (from notary.agentsystems.ai)
        slug: Tenant slug (e.g., "tnt_acme_corp")
        org_bucket_name: S3 bucket name for raw logs (organization's custody)
        api_url: Notary API endpoint (default: production)
        debug: Enable debug output (default: False)

    Example:
        ```python
        from agentsystems_notary import LangChainNotary
        from langchain_anthropic import ChatAnthropic

        callback = LangChainNotary(
            api_key="sk_asn_prod_...",
            slug="tnt_acme_corp",
            org_bucket_name="acme-llm-logs"
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
        slug: str,
        org_bucket_name: str,
        api_url: str = "https://notary-api.agentsystems.ai/v1/notary",
        debug: bool = False,
    ):
        # Initialize framework-agnostic core
        self.core = NotaryCore(
            api_key=api_key,
            slug=slug,
            org_bucket_name=org_bucket_name,
            api_url=api_url,
            debug=debug,
        )

        # Temporary storage for request data
        self.current_request: dict[str, Any] = {}

    def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        """Capture LLM request metadata."""
        self.current_request = {
            "prompts": prompts,
            "timestamp": kwargs.get("timestamp"),
            "model_config": kwargs.get("invocation_params", {}),
        }

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """
        Capture LLM response and log to Notary.

        Extracts response from LangChain's response object and calls
        the framework-agnostic core logging method.
        """
        # Extract response text from LangChain's response structure
        if response.generations:
            response_text = response.generations[0][0].text
        else:
            response_text = ""

        # Call framework-agnostic core
        self.core.log_interaction(
            input_data=self.current_request,
            output_data={"text": response_text},
            metadata={},
        )

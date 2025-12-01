"""AgentSystems Notary - Audit logging for LLM interactions."""

from importlib import metadata as _metadata

from .core import NotaryCore

__version__ = (
    _metadata.version(__name__.replace("_", "-")) if __name__ != "__main__" else "0.0.0"
)

__all__ = ["__version__", "NotaryCore"]

# Framework adapters (optional - only available if dependencies installed)
try:
    from .langchain_adapter import LangChainNotary  # noqa: F401

    __all__.append("LangChainNotary")
except ImportError:
    pass

try:
    from .crewai_adapter import CrewAINotary  # noqa: F401

    __all__.append("CrewAINotary")
except ImportError:
    pass

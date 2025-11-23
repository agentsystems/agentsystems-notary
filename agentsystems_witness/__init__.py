"""AgentSystems Witness - Audit logging for LLM interactions in regulated industries."""

from importlib import metadata as _metadata

__version__ = (
    _metadata.version(__name__.replace("_", "-")) if __name__ != "__main__" else "0.0.0"
)

# Core (always available)
from .core import WitnessCore

# Framework adapters (will raise ImportError if dependencies not installed)
from .langchain_adapter import LangChainWitness
from .crewai_adapter import CrewAIWitness

__all__ = ["__version__", "WitnessCore", "LangChainWitness", "CrewAIWitness"]

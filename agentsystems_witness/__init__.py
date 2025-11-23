"""AgentSystems Witness - Compliance logging for LLM audit trails."""

from importlib import metadata as _metadata

__version__ = (
    _metadata.version(__name__.replace("_", "-")) if __name__ != "__main__" else "0.0.0"
)

from .callback_handler import WitnessCallback

__all__ = ["__version__", "WitnessCallback"]

"""AgentSystems Notary - Audit logging for LLM interactions."""

from importlib import metadata as _metadata

from .arweave import BundlerError
from .config import (
    ArweaveHashStorage,
    AwsKmsSignerConfig,
    AwsS3StorageConfig,
    AzureBlobStorageConfig,
    AzureKeyVaultSignerConfig,
    CustodiedHashStorage,
    GcpCloudStorageConfig,
    GcpKmsSignerConfig,
    LocalKeySignerConfig,
    RawPayloadStorage,
    SignerConfig,
    StorageConfig,
)
from .core import LogResult, NotaryCore, PayloadTooLargeError

__version__ = (
    _metadata.version(__name__.replace("_", "-")) if __name__ != "__main__" else "0.0.0"
)

__all__ = [
    "__version__",
    "NotaryCore",
    "RawPayloadStorage",
    "CustodiedHashStorage",
    "ArweaveHashStorage",
    # Signer configs
    "AwsKmsSignerConfig",
    "GcpKmsSignerConfig",
    "AzureKeyVaultSignerConfig",
    "LocalKeySignerConfig",
    "SignerConfig",
    # Storage configs
    "AwsS3StorageConfig",
    "GcpCloudStorageConfig",
    "AzureBlobStorageConfig",
    "StorageConfig",
    # Results and errors
    "LogResult",
    "PayloadTooLargeError",
    "BundlerError",
]

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

try:
    from .llamaindex_adapter import LlamaIndexNotary  # noqa: F401

    __all__.append("LlamaIndexNotary")
except ImportError:
    pass

try:
    from .agno_adapter import AgnoNotary  # noqa: F401

    __all__.append("AgnoNotary")
except ImportError:
    pass

try:
    from .agent_control_adapter import AgentControlNotarySink  # noqa: F401

    __all__.append("AgentControlNotarySink")
except ImportError:
    pass

try:
    from .faramesh_adapter import FarameshNotarySink  # noqa: F401

    __all__.append("FarameshNotarySink")
except ImportError:
    pass

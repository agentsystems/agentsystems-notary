"""Configuration dataclasses for Notary SDK."""

from dataclasses import dataclass


@dataclass
class AwsKmsSignerConfig:
    """AWS KMS signer configuration.

    Args:
        kms_key_arn: AWS KMS key ARN for RSA-4096 signing
        aws_access_key_id: AWS access key for KMS operations
        aws_secret_access_key: AWS secret key for KMS operations
        aws_region: AWS region for KMS (default: us-east-1)
    """

    kms_key_arn: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"


@dataclass
class GcpKmsSignerConfig:
    """GCP Cloud KMS signer configuration.

    Args:
        key_resource_name: Full resource name (projects/.../locations/...
            /keyRings/.../cryptoKeys/.../cryptoKeyVersions/...)
        credentials_path: Path to service account JSON file
            (optional, uses ADC if not provided)
    """

    key_resource_name: str
    credentials_path: str | None = None


@dataclass
class AzureKeyVaultSignerConfig:
    """Azure Key Vault signer configuration.

    Args:
        vault_url: Key Vault URL (https://<vault-name>.vault.azure.net)
        key_name: Name of the signing key
        key_version: Specific key version (optional, uses latest if not provided)
    """

    vault_url: str
    key_name: str
    key_version: str | None = None


@dataclass
class LocalKeySignerConfig:
    """Local private key signer configuration.

    Exactly one of private_key_path or private_key_env_var must be provided.

    Args:
        private_key_path: Path to PEM file containing RSA-4096 private key
        private_key_env_var: Environment variable name containing PEM-encoded key
    """

    private_key_path: str | None = None
    private_key_env_var: str | None = None


# Union type for signer configs
SignerConfig = (
    AwsKmsSignerConfig
    | GcpKmsSignerConfig
    | AzureKeyVaultSignerConfig
    | LocalKeySignerConfig
)


@dataclass
class AwsS3StorageConfig:
    """AWS S3 storage configuration.

    Args:
        bucket_name: S3 bucket name for storing payloads
        aws_access_key_id: AWS access key for S3 operations
        aws_secret_access_key: AWS secret key for S3 operations
        aws_region: AWS region (default: us-east-1)
    """

    bucket_name: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"


@dataclass
class GcpCloudStorageConfig:
    """GCP Cloud Storage configuration.

    Status: Under development. Not yet available for use.

    Args:
        bucket_name: GCS bucket name
        credentials_path: Path to service account JSON file
            (optional, uses ADC if not provided)
    """

    bucket_name: str
    credentials_path: str | None = None


@dataclass
class AzureBlobStorageConfig:
    """Azure Blob Storage configuration.

    Status: Under development. Not yet available for use.

    Args:
        container_url: Blob container URL
        container_name: Name of the blob container
    """

    container_url: str
    container_name: str


# Union type for storage configs
StorageConfig = AwsS3StorageConfig | GcpCloudStorageConfig | AzureBlobStorageConfig


@dataclass
class RawPayloadStorage:
    """
    Configuration for raw payload storage (vendor's bucket for full audit logs).

    The vendor's bucket receives the full JSON payload of every LLM interaction.
    This is where the raw audit logs are stored for verification.

    Supports multiple storage backends:
    - AWS S3 (AwsS3StorageConfig)
    - GCP Cloud Storage (GcpCloudStorageConfig) - coming soon
    - Azure Blob Storage (AzureBlobStorageConfig) - coming soon

    Args:
        storage: Storage configuration (one of the StorageConfig types)
    """

    storage: StorageConfig


@dataclass
class CustodiedHashStorage:
    """
    Configuration for AgentSystems custodied hash storage (centralized).

    Hashes are sent to the AgentSystems API for tamper-evident storage.
    The API returns a receipt and tenant_id for verification.

    Args:
        api_key: AgentSystems API key (sk_asn_test_* or sk_asn_prod_*)
        slug: Tenant slug (human-readable identifier, e.g., "tnt_acme_corp")
        api_url: API endpoint (default: production)
    """

    api_key: str
    slug: str
    api_url: str = "https://notary-api.agentsystems.ai/v1/notary"


@dataclass
class ArweaveHashStorage:
    """
    Configuration for Arweave blockchain hash storage.

    Hashes are signed and uploaded to Arweave via a bundler.
    This provides decentralized, immutable verification without AgentSystems dependency.

    Supports multiple signing backends:
    - AWS KMS (AwsKmsSignerConfig)
    - GCP Cloud KMS (GcpKmsSignerConfig)
    - Azure Key Vault (AzureKeyVaultSignerConfig)
    - Local RSA-4096 private key (LocalKeySignerConfig)

    Args:
        namespace: Anonymous identifier for enterprise customer (no PII)
        signer: Signer configuration (one of the SignerConfig types)
        bundler_url: Arweave bundler endpoint
        explorer_url: Arweave explorer URL for debug output (optional)
    """

    namespace: str
    signer: SignerConfig
    bundler_url: str
    explorer_url: str | None = None

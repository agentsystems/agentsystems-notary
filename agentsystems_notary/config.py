"""Configuration dataclasses for Notary SDK."""

from dataclasses import dataclass


@dataclass
class RawPayloadStorage:
    """
    Configuration for raw payload storage (vendor's S3 bucket for full audit logs).

    The vendor's S3 bucket receives the full JSON payload of every LLM interaction.
    This is where the raw audit logs are stored for verification.

    Args:
        bucket_name: S3 bucket name for storing full audit payloads
        aws_access_key_id: AWS access key for S3 operations
        aws_secret_access_key: AWS secret key for S3 operations
        aws_region: AWS region (default: us-east-1)
    """

    bucket_name: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"


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

    Hashes are signed with AWS KMS and uploaded to Arweave via a bundler.
    This provides decentralized, immutable verification without AgentSystems dependency.

    Args:
        namespace: Anonymous identifier for enterprise customer (no PII)
        kms_key_arn: AWS KMS key ARN for RSA-4096 signing
        aws_access_key_id: AWS access key for KMS operations
        aws_secret_access_key: AWS secret key for KMS operations
        bundler_url: Arweave bundler endpoint
        aws_region: AWS region for KMS (default: us-east-1)
        explorer_url: Arweave explorer URL for debug output (optional)
    """

    namespace: str
    kms_key_arn: str
    aws_access_key_id: str
    aws_secret_access_key: str
    bundler_url: str
    aws_region: str = "us-east-1"
    explorer_url: str | None = None

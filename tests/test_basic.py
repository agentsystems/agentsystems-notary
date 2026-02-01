"""Basic tests for agentsystems-notary."""

import pytest

from agentsystems_notary import (
    ArweaveHashStorage,
    AwsKmsSignerConfig,
    AwsS3StorageConfig,
    AzureBlobStorageConfig,
    AzureKeyVaultSignerConfig,
    CustodiedHashStorage,
    GcpCloudStorageConfig,
    GcpKmsSignerConfig,
    LocalKeySignerConfig,
    LogResult,
    NotaryCore,
    PayloadTooLargeError,
    RawPayloadStorage,
    __version__,
)


# Helpers
def make_raw_payload_storage() -> RawPayloadStorage:
    return RawPayloadStorage(
        storage=AwsS3StorageConfig(
            bucket_name="test-bucket",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
        ),
    )


def make_custodied_storage(api_key: str = "sk_asn_test_key") -> CustodiedHashStorage:
    return CustodiedHashStorage(
        api_key=api_key,
        slug="test_tenant",
    )


def make_arweave_storage() -> ArweaveHashStorage:
    return ArweaveHashStorage(
        namespace="test-namespace",
        signer=AwsKmsSignerConfig(
            kms_key_arn="arn:aws:kms:us-east-1:123:key/abc",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
        ),
        bundler_url="https://test-bundler.example.com",
    )


def test_version() -> None:
    """Test version is defined."""
    assert __version__ is not None


def test_raw_payload_storage() -> None:
    """Test RawPayloadStorage dataclass with AWS S3 storage."""
    storage_config = AwsS3StorageConfig(
        bucket_name="my-bucket",
        aws_access_key_id="AKIA...",
        aws_secret_access_key="secret",
    )
    config = RawPayloadStorage(storage=storage_config)
    assert isinstance(config.storage, AwsS3StorageConfig)
    assert config.storage.bucket_name == "my-bucket"
    assert config.storage.aws_region == "us-east-1"  # default


def test_gcp_cloud_storage_config() -> None:
    """Test GcpCloudStorageConfig dataclass."""
    config = GcpCloudStorageConfig(
        bucket_name="my-gcs-bucket",
    )
    assert config.bucket_name == "my-gcs-bucket"
    assert config.credentials_path is None  # Uses ADC by default


def test_azure_blob_storage_config() -> None:
    """Test AzureBlobStorageConfig dataclass."""
    config = AzureBlobStorageConfig(
        container_url="https://myaccount.blob.core.windows.net",
        container_name="my-container",
    )
    assert config.container_url == "https://myaccount.blob.core.windows.net"
    assert config.container_name == "my-container"


def test_gcp_storage_not_implemented() -> None:
    """Test GcpCloudStorage raises NotImplementedError (under development)."""
    from agentsystems_notary.storage import GcpCloudStorage

    config = GcpCloudStorageConfig(bucket_name="test-bucket")
    with pytest.raises(NotImplementedError, match="under development"):
        GcpCloudStorage(config)


def test_azure_storage_not_implemented() -> None:
    """Test AzureBlobStorage raises NotImplementedError (under development)."""
    from agentsystems_notary.storage import AzureBlobStorage

    config = AzureBlobStorageConfig(
        container_url="https://test.blob.core.windows.net",
        container_name="test",
    )
    with pytest.raises(NotImplementedError, match="under development"):
        AzureBlobStorage(config)


def test_custodied_hash_storage() -> None:
    """Test CustodiedHashStorage dataclass."""
    storage = CustodiedHashStorage(
        api_key="sk_asn_test_key",
        slug="my_tenant",
    )
    assert storage.api_key == "sk_asn_test_key"
    assert storage.slug == "my_tenant"
    assert storage.api_url == "https://notary-api.agentsystems.ai/v1/notary"


def test_arweave_hash_storage() -> None:
    """Test ArweaveHashStorage dataclass with AWS KMS signer."""
    signer = AwsKmsSignerConfig(
        kms_key_arn="arn:aws:kms:us-east-1:123:key/abc",
        aws_access_key_id="AKIA...",
        aws_secret_access_key="secret",
    )
    storage = ArweaveHashStorage(
        namespace="my-namespace",
        signer=signer,
        bundler_url="https://test-bundler.example.com",
    )
    assert storage.namespace == "my-namespace"
    assert isinstance(storage.signer, AwsKmsSignerConfig)
    assert storage.signer.kms_key_arn == "arn:aws:kms:us-east-1:123:key/abc"
    assert storage.bundler_url == "https://test-bundler.example.com"


def test_gcp_kms_signer_config() -> None:
    """Test GcpKmsSignerConfig dataclass."""
    config = GcpKmsSignerConfig(
        key_resource_name="projects/my-project/locations/us/keyRings/my-ring/cryptoKeys/my-key/cryptoKeyVersions/1",
    )
    assert config.key_resource_name.startswith("projects/")
    assert config.credentials_path is None  # Uses ADC by default


def test_azure_key_vault_signer_config() -> None:
    """Test AzureKeyVaultSignerConfig dataclass."""
    config = AzureKeyVaultSignerConfig(
        vault_url="https://my-vault.vault.azure.net",
        key_name="my-signing-key",
    )
    assert config.vault_url == "https://my-vault.vault.azure.net"
    assert config.key_name == "my-signing-key"
    assert config.key_version is None  # Uses latest by default


def test_local_key_signer_config() -> None:
    """Test LocalKeySignerConfig dataclass."""
    config_path = LocalKeySignerConfig(private_key_path="/path/to/key.pem")
    assert config_path.private_key_path == "/path/to/key.pem"
    assert config_path.private_key_env_var is None

    config_env = LocalKeySignerConfig(private_key_env_var="NOTARY_PRIVATE_KEY")
    assert config_env.private_key_path is None
    assert config_env.private_key_env_var == "NOTARY_PRIVATE_KEY"


def test_arweave_storage_with_gcp_signer() -> None:
    """Test ArweaveHashStorage with GCP KMS signer."""
    storage = ArweaveHashStorage(
        namespace="my-namespace",
        signer=GcpKmsSignerConfig(
            key_resource_name="projects/my-project/locations/us/keyRings/my-ring/cryptoKeys/my-key/cryptoKeyVersions/1",
        ),
        bundler_url="https://test-bundler.example.com",
    )
    assert isinstance(storage.signer, GcpKmsSignerConfig)


def test_arweave_storage_with_azure_signer() -> None:
    """Test ArweaveHashStorage with Azure Key Vault signer."""
    storage = ArweaveHashStorage(
        namespace="my-namespace",
        signer=AzureKeyVaultSignerConfig(
            vault_url="https://my-vault.vault.azure.net",
            key_name="my-signing-key",
        ),
        bundler_url="https://test-bundler.example.com",
    )
    assert isinstance(storage.signer, AzureKeyVaultSignerConfig)


def test_arweave_storage_with_local_signer() -> None:
    """Test ArweaveHashStorage with local key signer."""
    storage = ArweaveHashStorage(
        namespace="my-namespace",
        signer=LocalKeySignerConfig(private_key_path="/path/to/key.pem"),
        bundler_url="https://test-bundler.example.com",
    )
    assert isinstance(storage.signer, LocalKeySignerConfig)


def test_gcp_signer_not_implemented() -> None:
    """Test GcpKmsSigner raises NotImplementedError (under development)."""
    from agentsystems_notary.signing import GcpKmsSigner

    config = GcpKmsSignerConfig(
        key_resource_name="projects/test/locations/us/keyRings/ring/cryptoKeys/key/cryptoKeyVersions/1",
    )
    with pytest.raises(NotImplementedError, match="under development"):
        GcpKmsSigner(config)


def test_azure_signer_not_implemented() -> None:
    """Test AzureKeyVaultSigner raises NotImplementedError (under development)."""
    from agentsystems_notary.signing import AzureKeyVaultSigner

    config = AzureKeyVaultSignerConfig(
        vault_url="https://test.vault.azure.net",
        key_name="test-key",
    )
    with pytest.raises(NotImplementedError, match="under development"):
        AzureKeyVaultSigner(config)


def test_notary_core_requires_hash_storage() -> None:
    """Test NotaryCore requires at least one hash_storage."""
    with pytest.raises(ValueError, match="At least one hash_storage"):
        NotaryCore(
            raw_payload_storage=make_raw_payload_storage(),
            hash_storage=[],
        )


def test_notary_core_with_custodied_storage() -> None:
    """Test NotaryCore with CustodiedHashStorage."""
    core = NotaryCore(
        raw_payload_storage=make_raw_payload_storage(),
        hash_storage=[make_custodied_storage()],
    )
    assert len(core._custodied_storages) == 1
    assert len(core._arweave_storages) == 0
    assert core.is_test_mode is True


def test_notary_core_with_arweave_storage() -> None:
    """Test NotaryCore with ArweaveHashStorage."""
    core = NotaryCore(
        raw_payload_storage=make_raw_payload_storage(),
        hash_storage=[make_arweave_storage()],
    )
    assert len(core._custodied_storages) == 0
    assert len(core._arweave_storages) == 1


def test_notary_core_with_both_storages() -> None:
    """Test NotaryCore with both hash storages."""
    core = NotaryCore(
        raw_payload_storage=make_raw_payload_storage(),
        hash_storage=[make_custodied_storage(), make_arweave_storage()],
    )
    assert len(core._custodied_storages) == 1
    assert len(core._arweave_storages) == 1


def test_notary_core_prod_mode() -> None:
    """Test NotaryCore detects production mode."""
    core = NotaryCore(
        raw_payload_storage=make_raw_payload_storage(),
        hash_storage=[make_custodied_storage(api_key="sk_asn_prod_key")],
    )
    assert core.is_test_mode is False


def test_notary_core_test_mode() -> None:
    """Test NotaryCore detects test mode."""
    core = NotaryCore(
        raw_payload_storage=make_raw_payload_storage(),
        hash_storage=[make_custodied_storage(api_key="sk_asn_test_key")],
    )
    assert core.is_test_mode is True


def test_log_result_dataclass() -> None:
    """Test LogResult dataclass."""
    result = LogResult(
        content_hash="abc123",
        custodied_receipt="receipt123",
        arweave_tx_id="tx123",
    )
    assert result.content_hash == "abc123"
    assert result.custodied_receipt == "receipt123"
    assert result.arweave_tx_id == "tx123"


def test_log_result_defaults() -> None:
    """Test LogResult dataclass with defaults."""
    result = LogResult(content_hash="abc123")
    assert result.content_hash == "abc123"
    assert result.custodied_receipt is None
    assert result.arweave_tx_id is None


def test_payload_too_large_error() -> None:
    """Test PayloadTooLargeError can be raised."""
    with pytest.raises(PayloadTooLargeError):
        raise PayloadTooLargeError("test error")


def test_session_id_generated() -> None:
    """Test NotaryCore generates unique session_id."""
    core1 = NotaryCore(
        raw_payload_storage=make_raw_payload_storage(),
        hash_storage=[make_custodied_storage()],
    )
    core2 = NotaryCore(
        raw_payload_storage=make_raw_payload_storage(),
        hash_storage=[make_custodied_storage()],
    )
    assert core1.session_id != core2.session_id


def test_sequence_starts_at_zero() -> None:
    """Test NotaryCore sequence starts at 0."""
    core = NotaryCore(
        raw_payload_storage=make_raw_payload_storage(),
        hash_storage=[make_custodied_storage()],
    )
    assert core.sequence == 0

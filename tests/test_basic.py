"""Basic tests for agentsystems-notary."""

import pytest

from agentsystems_notary import (
    ArweaveHashStorage,
    CustodiedHashStorage,
    LogResult,
    NotaryCore,
    PayloadTooLargeError,
    RawPayloadStorage,
    __version__,
)


# Helpers
def make_raw_payload_storage() -> RawPayloadStorage:
    return RawPayloadStorage(
        bucket_name="test-bucket",
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",
    )


def make_custodied_storage(api_key: str = "sk_asn_test_key") -> CustodiedHashStorage:
    return CustodiedHashStorage(
        api_key=api_key,
        slug="test_tenant",
    )


def make_arweave_storage() -> ArweaveHashStorage:
    return ArweaveHashStorage(
        namespace="test-namespace",
        kms_key_arn="arn:aws:kms:us-east-1:123:key/abc",
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",
        bundler_url="https://test-bundler.example.com",
    )


def test_version() -> None:
    """Test version is defined."""
    assert __version__ is not None


def test_raw_payload_storage() -> None:
    """Test RawPayloadStorage dataclass."""
    config = RawPayloadStorage(
        bucket_name="my-bucket",
        aws_access_key_id="AKIA...",
        aws_secret_access_key="secret",
    )
    assert config.bucket_name == "my-bucket"
    assert config.aws_region == "us-east-1"  # default


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
    """Test ArweaveHashStorage dataclass."""
    storage = ArweaveHashStorage(
        namespace="my-namespace",
        kms_key_arn="arn:aws:kms:us-east-1:123:key/abc",
        aws_access_key_id="AKIA...",
        aws_secret_access_key="secret",
        bundler_url="https://test-bundler.example.com",
    )
    assert storage.namespace == "my-namespace"
    assert storage.kms_key_arn == "arn:aws:kms:us-east-1:123:key/abc"
    assert storage.bundler_url == "https://test-bundler.example.com"


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

"""Basic tests for agentsystems-notary."""

from agentsystems_notary import NotaryCore, __version__


def test_version():
    """Test version is defined."""
    assert __version__ is not None


def test_notary_core_init():
    """Test NotaryCore initialization."""
    core = NotaryCore(
        api_key="sk_asn_test_key",
        slug="test_tenant",
        org_bucket_name="test-bucket",
    )

    assert core.api_key == "sk_asn_test_key"
    assert core.slug == "test_tenant"
    assert core.bucket_name == "test-bucket"
    assert core.sequence == 0
    assert core.session_id is not None
    assert core.is_test_mode is True


def test_notary_core_prod_mode():
    """Test NotaryCore detects production mode."""
    core = NotaryCore(
        api_key="sk_asn_prod_key",
        slug="test_tenant",
        org_bucket_name="test-bucket",
    )

    assert core.is_test_mode is False


def test_notary_core_with_custom_url():
    """Test NotaryCore with custom API URL."""
    core = NotaryCore(
        api_key="sk_asn_test_key",
        slug="test_tenant",
        org_bucket_name="test-bucket",
        api_url="http://localhost:8000/v1/notary",
    )

    assert core.api_url == "http://localhost:8000/v1/notary"


def test_notary_core_debug_mode():
    """Test NotaryCore debug mode."""
    core = NotaryCore(
        api_key="sk_asn_test_key",
        slug="test_tenant",
        org_bucket_name="test-bucket",
        debug=True,
    )

    assert core.debug is True

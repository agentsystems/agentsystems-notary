"""Basic tests for agentsystems-notary."""

import pytest
from agentsystems_notary import LangChainNotary, __version__


def test_version():
    """Test version is defined."""
    assert __version__ is not None


def test_langchain_notary_init():
    """Test LangChainNotary initialization."""
    notary = LangChainNotary(
        api_key="test_key",
        slug="test_tenant",
        vendor_bucket_name="test-bucket"
    )

    assert notary.core.api_key == "test_key"
    assert notary.core.slug == "test_tenant"
    assert notary.core.bucket_name == "test-bucket"
    assert notary.core.sequence == 0
    assert notary.core.session_id is not None


def test_langchain_notary_with_custom_url():
    """Test LangChainNotary with custom API URL."""
    notary = LangChainNotary(
        api_key="test_key",
        slug="test_tenant",
        vendor_bucket_name="test-bucket",
        api_url="http://localhost:8000/v1/notary"
    )

    assert notary.core.api_url == "http://localhost:8000/v1/notary"


def test_langchain_notary_debug_mode():
    """Test LangChainNotary debug mode."""
    notary = LangChainNotary(
        api_key="test_key",
        slug="test_tenant",
        vendor_bucket_name="test-bucket",
        debug=True
    )

    assert notary.core.debug is True

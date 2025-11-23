"""Basic tests for agentsystems-witness."""

import pytest
from agentsystems_witness import WitnessCallback, __version__


def test_version():
    """Test version is defined."""
    assert __version__ is not None


def test_witness_callback_init():
    """Test WitnessCallback initialization."""
    callback = WitnessCallback(
        api_key="test_key",
        tenant_id="test_tenant",
        vendor_bucket_name="test-bucket"
    )

    assert callback.api_key == "test_key"
    assert callback.tenant_id == "test_tenant"
    assert callback.bucket_name == "test-bucket"
    assert callback.sequence == 0
    assert callback.session_id is not None


def test_witness_callback_with_custom_url():
    """Test WitnessCallback with custom API URL."""
    callback = WitnessCallback(
        api_key="test_key",
        tenant_id="test_tenant",
        vendor_bucket_name="test-bucket",
        api_url="http://localhost:8000/v1/witness"
    )

    assert callback.api_url == "http://localhost:8000/v1/witness"


def test_witness_callback_debug_mode():
    """Test WitnessCallback debug mode."""
    callback = WitnessCallback(
        api_key="test_key",
        tenant_id="test_tenant",
        vendor_bucket_name="test-bucket",
        debug=True
    )

    assert callback.debug is True

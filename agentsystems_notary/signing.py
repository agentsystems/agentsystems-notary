"""Pluggable signing module for multi-cloud support.

This module provides a Signer protocol and implementations for various
key management systems: AWS KMS, GCP Cloud KMS, Azure Key Vault, and local keys.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Protocol

import boto3
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import (
    load_der_public_key,
    load_pem_private_key,
)

if TYPE_CHECKING:
    from .config import (
        AwsKmsSignerConfig,
        AzureKeyVaultSignerConfig,
        GcpKmsSignerConfig,
        LocalKeySignerConfig,
        SignerConfig,
    )


class Signer(Protocol):
    """Protocol for RSA-4096 signers used in Arweave data items."""

    def get_owner(self) -> bytes:
        """Return 512-byte RSA-4096 public key modulus."""
        ...

    def sign(self, message: bytes) -> bytes:
        """Sign message with RSASSA_PSS_SHA_256, return 512-byte signature."""
        ...


class AwsKmsSigner:
    """AWS KMS RSA-4096 signer implementation."""

    def __init__(self, config: AwsKmsSignerConfig) -> None:
        self._config = config
        self._session: Any = None
        self._owner: bytes | None = None

    def _get_session(self) -> Any:
        """Lazy-init boto3 session with explicit credentials."""
        if self._session is None:
            self._session = boto3.Session(
                aws_access_key_id=self._config.aws_access_key_id,
                aws_secret_access_key=self._config.aws_secret_access_key,
                region_name=self._config.aws_region,
            )
        return self._session

    def get_owner(self) -> bytes:
        """Fetch and cache KMS public key modulus (owner)."""
        if self._owner is None:
            session = self._get_session()
            kms = session.client("kms", region_name=self._config.aws_region)
            response = kms.get_public_key(KeyId=self._config.kms_key_arn)

            # Parse DER-encoded public key to extract RSA modulus
            der_bytes = response["PublicKey"]
            pub = load_der_public_key(der_bytes)
            n = pub.public_numbers().n  # type: ignore[union-attr]

            # Convert modulus to bytes (512 bytes for RSA-4096)
            n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
            self._owner = n_bytes

        return self._owner

    def sign(self, message: bytes) -> bytes:
        """Sign a message using AWS KMS with RSASSA_PSS_SHA_256."""
        session = self._get_session()
        kms = session.client("kms", region_name=self._config.aws_region)
        response = kms.sign(
            KeyId=self._config.kms_key_arn,
            Message=message,
            MessageType="RAW",
            SigningAlgorithm="RSASSA_PSS_SHA_256",
        )
        signature: bytes = response["Signature"]
        return signature


class GcpKmsSigner:
    """GCP Cloud KMS RSA-4096 signer implementation.

    Status: Under development. Not yet available for use.
    """

    def __init__(self, config: GcpKmsSignerConfig) -> None:
        raise NotImplementedError(
            "GCP Cloud KMS signer is under development. "
            "Please use AwsKmsSignerConfig or LocalKeySignerConfig for now."
        )

    def get_owner(self) -> bytes:
        """Fetch and cache GCP KMS public key modulus (owner)."""
        raise NotImplementedError("GCP Cloud KMS signer is under development.")

    def sign(self, message: bytes) -> bytes:
        """Sign a message using GCP Cloud KMS with RSA_PSS_SHA256."""
        raise NotImplementedError("GCP Cloud KMS signer is under development.")


class AzureKeyVaultSigner:
    """Azure Key Vault RSA-4096 signer implementation.

    Status: Under development. Not yet available for use.
    """

    def __init__(self, config: AzureKeyVaultSignerConfig) -> None:
        raise NotImplementedError(
            "Azure Key Vault signer is under development. "
            "Please use AwsKmsSignerConfig or LocalKeySignerConfig for now."
        )

    def get_owner(self) -> bytes:
        """Fetch and cache Azure Key Vault public key modulus (owner)."""
        raise NotImplementedError("Azure Key Vault signer is under development.")

    def sign(self, message: bytes) -> bytes:
        """Sign a message using Azure Key Vault with PS256 (RSA-PSS with SHA-256)."""
        raise NotImplementedError("Azure Key Vault signer is under development.")


class LocalKeySigner:
    """Local RSA-4096 private key signer implementation.

    Loads key from a PEM file or environment variable.
    """

    _private_key: rsa.RSAPrivateKey

    def __init__(self, config: LocalKeySignerConfig) -> None:
        self._owner: bytes | None = None

        # Load private key from file or environment variable
        if config.private_key_path and config.private_key_env_var:
            raise ValueError(
                "Specify either private_key_path or private_key_env_var, not both"
            )
        if not config.private_key_path and not config.private_key_env_var:
            raise ValueError(
                "Must specify either private_key_path or private_key_env_var"
            )

        if config.private_key_path:
            with open(config.private_key_path, "rb") as f:
                pem_data = f.read()
        else:
            env_value = os.environ.get(config.private_key_env_var or "")
            if not env_value:
                raise ValueError(
                    f"Environment variable {config.private_key_env_var} not set"
                )
            pem_data = env_value.encode("utf-8")

        loaded_key = load_pem_private_key(pem_data, password=None)

        # Verify it's RSA-4096
        if not isinstance(loaded_key, rsa.RSAPrivateKey):
            raise ValueError("Private key must be RSA")
        if loaded_key.key_size != 4096:
            key_size = loaded_key.key_size
            raise ValueError(f"Private key must be RSA-4096, got RSA-{key_size}")

        self._private_key = loaded_key

    def get_owner(self) -> bytes:
        """Get RSA public key modulus (owner)."""
        if self._owner is None:
            pub = self._private_key.public_key()
            n = pub.public_numbers().n

            # Convert modulus to bytes (512 bytes for RSA-4096)
            n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
            self._owner = n_bytes

        return self._owner

    def sign(self, message: bytes) -> bytes:
        """Sign a message with RSASSA-PSS-SHA256."""
        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                # Use hash length (32 bytes) to match AWS KMS behavior
                salt_length=hashes.SHA256.digest_size,
            ),
            hashes.SHA256(),
        )
        return signature


def create_signer(config: SignerConfig) -> Signer:
    """Factory function to create a Signer from configuration."""
    # Import here to avoid circular imports
    from .config import (
        AwsKmsSignerConfig,
        AzureKeyVaultSignerConfig,
        GcpKmsSignerConfig,
        LocalKeySignerConfig,
    )

    if isinstance(config, AwsKmsSignerConfig):
        return AwsKmsSigner(config)
    elif isinstance(config, GcpKmsSignerConfig):
        return GcpKmsSigner(config)
    elif isinstance(config, AzureKeyVaultSignerConfig):
        return AzureKeyVaultSigner(config)
    elif isinstance(config, LocalKeySignerConfig):
        return LocalKeySigner(config)
    else:
        raise ValueError(f"Unknown signer config type: {type(config)}")

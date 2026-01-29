"""Arweave backend for hash storage via ANS-104 data items."""

import base64
import hashlib
import json
import struct
from datetime import UTC, datetime
from importlib import metadata

import boto3
import requests
from cryptography.hazmat.primitives.serialization import load_der_public_key

from .config import ArweaveHashStorage

try:
    __version__ = metadata.version("agentsystems-notary")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0"


def b64url_encode(data: bytes) -> str:
    """Encode bytes to base64url without padding."""
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def sha256(data: bytes) -> bytes:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data).digest()


def sha384(data: bytes) -> bytes:
    """Compute SHA-384 hash."""
    return hashlib.sha384(data).digest()


def deep_hash(data: bytes | list) -> bytes:  # type: ignore[type-arg]
    """
    Arweave deep hash algorithm using SHA-384.

    Used to create the message to sign for ANS-104 data items.
    """
    if isinstance(data, bytes | bytearray):
        data = bytes(data)
        tag = b"blob" + str(len(data)).encode()
        return sha384(sha384(tag) + sha384(data))
    if isinstance(data, list):
        tag = b"list" + str(len(data)).encode()
        acc = sha384(tag)
        for item in data:
            acc = sha384(acc + deep_hash(item))
        return acc
    raise TypeError(f"Unsupported type: {type(data)}")


def avro_long(n: int) -> bytes:
    """Encode non-negative integer as Avro long (zigzag + varint)."""
    zz = n << 1  # zigzag for non-negative
    out = bytearray()
    while True:
        b = zz & 0x7F
        zz >>= 7
        out.append(b | (0x80 if zz else 0))
        if not zz:
            break
    return bytes(out)


def encode_tags(tags: list[tuple[bytes, bytes]]) -> bytes:
    """Encode tags in Avro format for ANS-104."""
    if not tags:
        return b""
    out = bytearray()
    out += avro_long(len(tags))  # count
    for name, value in tags:
        out += avro_long(len(name)) + name
        out += avro_long(len(value)) + value
    out += b"\x00"  # end of array
    return bytes(out)


class ArweaveBackend:
    """
    Backend for uploading hashes to Arweave via ANS-104 data items.

    Uses AWS KMS for RSA-4096 signing. The owner address (derived from the
    KMS public key) identifies the vendor on Arweave.
    """

    def __init__(self, storage: ArweaveHashStorage, debug: bool = False):
        self.storage = storage
        self.debug = debug
        self._session: boto3.Session | None = None
        self._owner: bytes | None = None  # Cached RSA modulus
        self._owner_address: str | None = None  # Cached base64url address

    def _get_session(self) -> boto3.Session:
        """Lazy-init boto3 session with explicit credentials."""
        if self._session is None:
            self._session = boto3.Session(
                aws_access_key_id=self.storage.aws_access_key_id,
                aws_secret_access_key=self.storage.aws_secret_access_key,
                region_name=self.storage.aws_region,
            )
        return self._session

    def _get_owner(self) -> bytes:
        """Fetch and cache KMS public key modulus (owner)."""
        if self._owner is None:
            session = self._get_session()
            kms = session.client("kms", region_name=self.storage.aws_region)
            response = kms.get_public_key(KeyId=self.storage.kms_key_arn)

            # Parse DER-encoded public key to extract RSA modulus
            der_bytes = response["PublicKey"]
            pub = load_der_public_key(der_bytes)
            n = pub.public_numbers().n  # type: ignore[union-attr]

            # Convert modulus to bytes (512 bytes for RSA-4096)
            n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
            self._owner = n_bytes

            if self.debug:
                print(f"[Arweave] Owner size: {len(n_bytes)} bytes")

        return self._owner

    def get_owner_address(self) -> str:
        """
        Get the Arweave owner address (for verification queries).

        This is derived from SHA256(RSA_modulus) and identifies the
        vendor's signing key on Arweave.
        """
        if self._owner_address is None:
            owner = self._get_owner()
            self._owner_address = b64url_encode(sha256(owner))
        return self._owner_address

    def _kms_sign(self, message: bytes) -> bytes:
        """Sign a message using AWS KMS with RSASSA_PSS_SHA_256."""
        session = self._get_session()
        kms = session.client("kms", region_name=self.storage.aws_region)
        response = kms.sign(
            KeyId=self.storage.kms_key_arn,
            Message=message,
            MessageType="RAW",
            SigningAlgorithm="RSASSA_PSS_SHA_256",
        )
        signature: bytes = response["Signature"]
        return signature

    def _build_data_item(
        self, data: bytes, owner: bytes, tags: list[tuple[str, str]]
    ) -> tuple[bytes, str]:
        """
        Build and sign an ANS-104 data item.

        Returns (serialized_data_item, data_item_id).
        """
        if len(owner) != 512:
            raise ValueError(
                f"Owner must be 512 bytes (RSA-4096 modulus), got {len(owner)}"
            )

        # Convert tags to bytes
        tags_bytes = [(name.encode(), value.encode()) for name, value in tags]
        tags_avro = encode_tags(tags_bytes)

        # Optional fields (empty for simplicity)
        target = b""
        anchor = b""

        # Build deep hash structure for signing
        # Format: ["dataitem", "1", signatureType, owner, target, anchor, tags, data]
        # signatureType = "1" for Arweave RSA-4096
        to_sign = deep_hash(
            [
                b"dataitem",
                b"1",
                b"1",  # signatureType as string
                owner,
                target,
                anchor,
                tags_avro if tags_avro else b"",
                data,
            ]
        )

        # Sign with KMS
        if self.debug:
            print("[Arweave] Signing with AWS KMS...")
        signature = self._kms_sign(to_sign)
        if len(signature) != 512:
            raise ValueError(f"Expected 512-byte signature, got {len(signature)}")

        # Data item ID = SHA256(signature)
        data_item_id = b64url_encode(sha256(signature))

        # Serialize ANS-104 data item (little-endian)
        out = bytearray()
        out += struct.pack("<H", 1)  # signature type = 1 (Arweave RSA-4096)
        out += signature  # 512 bytes
        out += owner  # 512 bytes
        out += b"\x00"  # target present = 0
        out += b"\x00"  # anchor present = 0
        out += struct.pack("<Q", len(tags_bytes))  # number of tags
        out += struct.pack("<Q", len(tags_avro))  # number of tag bytes
        out += tags_avro
        out += data

        return bytes(out), data_item_id

    def _upload_data_item(self, data_item: bytes) -> dict[str, str]:
        """Upload a signed data item to bundler."""
        if self.debug:
            url = self.storage.bundler_url
            print(f"[Arweave] Uploading {len(data_item)} bytes to {url}...")
        response = requests.post(
            self.storage.bundler_url,
            data=data_item,
            headers={"Content-Type": "application/octet-stream"},
            timeout=30,
        )
        response.raise_for_status()
        result: dict[str, str] = response.json()
        return result

    def upload_hash(
        self,
        content_hash: str,
        session_id: str,
        sequence: int,
    ) -> str:
        """
        Upload content hash to Arweave.

        Args:
            content_hash: SHA-256 hash of the canonical payload (hex string)
            session_id: UUID identifying the logging session
            sequence: Sequence number within the session

        Returns:
            Transaction ID (base64url encoded)
        """
        now = datetime.now(UTC)
        notarized_at = now.isoformat()
        notarized_date_utc = now.strftime("%Y-%m-%d")

        # Build receipt JSON
        receipt = {
            "hash": content_hash,
            "namespace": self.storage.namespace,
            "notarized_at": notarized_at,
            "sdk_version": __version__,
            "v": "1",
        }
        data = json.dumps(receipt).encode("utf-8")

        # Tags for discoverability
        tags = [
            ("App-Name", "agentsystems-notary"),
            ("Content-Type", "application/json"),
            ("Namespace", self.storage.namespace),
            ("Hash", content_hash),
            ("Session-ID", session_id),
            ("Sequence", str(sequence)),
            ("Notarized-At", notarized_at),
            ("Notarized-Date-UTC", notarized_date_utc),
            ("SDK-Version", __version__),
        ]

        owner = self._get_owner()
        data_item, data_item_id = self._build_data_item(data, owner, tags)
        result = self._upload_data_item(data_item)

        # Some bundlers return their own ID, use computed ID as fallback
        tx_id: str = result.get("id", data_item_id)

        if self.debug:
            print(f"[Arweave] Transaction ID: {tx_id}")
            if self.storage.explorer_url:
                print(f"[Arweave] View: {self.storage.explorer_url}{tx_id}")

        return tx_id

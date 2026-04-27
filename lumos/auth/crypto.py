import base64
import binascii
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


AUTH_PAYLOAD_VERSION = "LUMOS-AUTH-V1"


def decode_raw_public_key(public_key: str) -> bytes:
    try:
        raw = base64.b64decode(public_key, validate=True)
    except Exception as exc:
        raise ValueError("public_key must be base64 encoded") from exc

    if len(raw) != 32:
        raise ValueError("Ed25519 public_key must decode to 32 bytes")

    return raw


def compute_kid(public_key: str) -> str:
    return hashlib.sha256(decode_raw_public_key(public_key)).hexdigest()


def auth_payload(agent_id: str, kid: str, nonce: str, timestamp: int) -> bytes:
    return f"{AUTH_PAYLOAD_VERSION}\n{agent_id}\n{kid}\n{nonce}\n{timestamp}".encode("utf-8")


def verify_auth_signature(
    public_key: str,
    agent_id: str,
    kid: str,
    nonce: str,
    timestamp: int,
    signature: str,
) -> bool:
    try:
        raw_public_key = decode_raw_public_key(public_key)
        raw_signature = base64.b64decode(signature, validate=True)
        verifier = Ed25519PublicKey.from_public_bytes(raw_public_key)
        verifier.verify(raw_signature, auth_payload(agent_id, kid, nonce, timestamp))
        return True
    except (InvalidSignature, ValueError, binascii.Error):
        return False

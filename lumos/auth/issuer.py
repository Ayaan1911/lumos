import base64
import logging
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from lumos.config import settings


logger = logging.getLogger(__name__)


def _issuer_key_path() -> Path:
    return Path(settings.issuer_key_path)


def load_or_create_issuer_private_key() -> Ed25519PrivateKey:
    path = _issuer_key_path()
    if path.exists():
        stat_result = path.stat()
        if oct(stat_result.st_mode & 0o777) != oct(0o600):
            logger.warning(
                "Issuer key file %s has insecure permissions %s. Expected 0o600.",
                path,
                oct(stat_result.st_mode & 0o777),
            )
        raw = base64.b64decode(path.read_text(encoding="utf-8").strip(), validate=True)
        if len(raw) != 32:
            raise ValueError("Issuer private key file must contain a base64 encoded 32-byte key")
        return Ed25519PrivateKey.from_private_bytes(raw)

    path.parent.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    raw = private_key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    path.write_text(base64.b64encode(raw).decode("ascii"), encoding="utf-8")
    os.chmod(path, 0o600)
    return private_key


def public_key_for(private_key: Ed25519PrivateKey) -> Ed25519PublicKey:
    return private_key.public_key()


def raw_public_key(public_key: Ed25519PublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )

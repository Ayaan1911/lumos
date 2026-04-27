from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from lumos.config import settings
from lumos.db import repositories
from lumos.db.models import Capability, Session


ISSUER = "lumos"
ALGORITHM = "EdDSA"


class TokenValidationError(Exception):
    pass


def now_utc() -> datetime:
    return datetime.now(UTC)


def unix_seconds(value: datetime) -> int:
    return int(value.timestamp())


def _db_unix_seconds(value: datetime) -> int:
    return int(value.timestamp())


def create_session_token(
    private_key: Ed25519PrivateKey,
    agent_id: str,
    session_id: str,
    kid: str,
    issued_at: datetime,
    expires_at: datetime,
) -> str:
    claims = {
        "typ": "session",
        "iss": ISSUER,
        "sub": agent_id,
        "sid": session_id,
        "iat": unix_seconds(issued_at),
        "nbf": unix_seconds(issued_at),
        "exp": unix_seconds(expires_at),
        "kid": kid,
    }
    return jwt.encode(claims, private_key, algorithm=ALGORITHM)


def create_capability_token(
    private_key: Ed25519PrivateKey,
    agent_id: str,
    session_id: str,
    capability_id: str,
    audience: str,
    tools: list[str],
    constraints: dict,
    issued_at: datetime,
    expires_at: datetime,
) -> str:
    claims = {
        "typ": "capability",
        "iss": ISSUER,
        "sub": agent_id,
        "sid": session_id,
        "jti": capability_id,
        "aud": audience,
        "tools": tools,
        "constraints": constraints,
        "iat": unix_seconds(issued_at),
        "nbf": unix_seconds(issued_at),
        "exp": unix_seconds(expires_at),
    }
    return jwt.encode(claims, private_key, algorithm=ALGORITHM)


def new_session_id() -> str:
    return f"session:{uuid4()}"


def new_capability_id() -> str:
    return f"capability:{uuid4()}"


def default_session_expiry(issued_at: datetime) -> datetime:
    return issued_at + timedelta(seconds=settings.session_ttl_seconds)


def default_capability_expiry(issued_at: datetime, session: Session) -> datetime:
    requested = issued_at + timedelta(seconds=settings.capability_ttl_seconds)
    return min(requested, session.expires_at)


def _decode_session_token(public_key: Ed25519PublicKey, token: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["typ", "iss", "sub", "sid", "iat", "nbf", "exp", "kid"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenValidationError("invalid session token") from exc

    if claims.get("typ") != "session":
        raise TokenValidationError("token is not a session token")
    return claims


def _decode_capability_token(
    public_key: Ed25519PublicKey,
    token: str,
    audience: str | None = None,
) -> dict:
    try:
        kwargs = {
            "algorithms": [ALGORITHM],
            "issuer": ISSUER,
            "options": {"require": ["typ", "iss", "sub", "sid", "jti", "aud", "tools", "constraints", "iat", "nbf", "exp"]},
        }
        if audience is None:
            kwargs["options"]["verify_aud"] = False
            claims = jwt.decode(token, public_key, **kwargs)
        else:
            claims = jwt.decode(token, public_key, audience=audience, **kwargs)
    except jwt.PyJWTError as exc:
        raise TokenValidationError("invalid capability token") from exc

    if claims.get("typ") != "capability":
        raise TokenValidationError("token is not a capability token")
    if not isinstance(claims.get("tools"), list):
        raise TokenValidationError("capability tools must be a list")
    if not isinstance(claims.get("constraints"), dict):
        raise TokenValidationError("capability constraints must be an object")
    return claims


async def validate_session_token(
    conn: asyncpg.Connection,
    issuer_public_key: Ed25519PublicKey,
    token: str,
) -> tuple[dict, Session]:
    claims = _decode_session_token(issuer_public_key, token)
    session = await repositories.get_session(conn, claims["sid"])
    if session is None:
        raise TokenValidationError("session not found")
    if session.status != "active":
        raise TokenValidationError("session is not active")
    if session.agent_id != claims["sub"]:
        raise TokenValidationError("session subject mismatch")
    if session.kid != claims["kid"]:
        raise TokenValidationError("session key mismatch")
    if abs(_db_unix_seconds(session.issued_at) - claims["iat"]) > 1:
        raise TokenValidationError("session issued-at mismatch")
    if abs(_db_unix_seconds(session.expires_at) - claims["exp"]) > 1:
        raise TokenValidationError("session expiration mismatch")
    if session.expires_at <= now_utc():
        raise TokenValidationError("session expired")

    agent = await repositories.get_agent(conn, session.agent_id)
    if agent is None or agent.status != "active":
        raise TokenValidationError("agent is not active")

    key = await repositories.get_agent_key(conn, session.agent_id, session.kid)
    if key is None or key.status != "active":
        raise TokenValidationError("session key is not active")

    return claims, session


async def validate_capability_token(
    conn: asyncpg.Connection,
    issuer_public_key: Ed25519PublicKey,
    token: str,
    audience: str | None = None,
) -> tuple[dict, Capability]:
    claims = _decode_capability_token(issuer_public_key, token, audience)
    capability = await repositories.get_capability(conn, claims["jti"])
    if capability is None:
        raise TokenValidationError("capability not found")
    if capability.status != "active":
        raise TokenValidationError("capability is not active")
    if capability.agent_id != claims["sub"]:
        raise TokenValidationError("capability subject mismatch")
    if capability.session_id != claims["sid"]:
        raise TokenValidationError("capability session mismatch")
    if capability.audience != claims["aud"]:
        raise TokenValidationError("capability audience mismatch")
    if audience is not None and capability.audience != audience:
        raise TokenValidationError("capability audience mismatch")
    if capability.tools != claims["tools"]:
        raise TokenValidationError("capability tools mismatch")
    if capability.constraints != claims["constraints"]:
        raise TokenValidationError("capability constraints mismatch")
    if abs(_db_unix_seconds(capability.issued_at) - claims["iat"]) > 1:
        raise TokenValidationError("capability issued-at mismatch")
    if abs(_db_unix_seconds(capability.expires_at) - claims["exp"]) > 1:
        raise TokenValidationError("capability expiration mismatch")
    if capability.expires_at <= now_utc():
        raise TokenValidationError("capability expired")

    session = await repositories.get_session(conn, capability.session_id)
    if session is None or session.status != "active":
        raise TokenValidationError("session is not active")
    if session.agent_id != capability.agent_id:
        raise TokenValidationError("session agent mismatch")
    if capability.expires_at > session.expires_at:
        raise TokenValidationError("capability exceeds session expiration")
    if session.expires_at <= now_utc():
        raise TokenValidationError("session expired")

    agent = await repositories.get_agent(conn, capability.agent_id)
    if agent is None or agent.status != "active":
        raise TokenValidationError("agent is not active")

    key = await repositories.get_agent_key(conn, session.agent_id, session.kid)
    if key is None or key.status != "active":
        raise TokenValidationError("session key is not active")

    return claims, capability

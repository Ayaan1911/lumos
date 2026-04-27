import base64
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from lumos.auth.crypto import auth_payload, compute_kid, verify_auth_signature
from lumos.auth.tokens import (
    TokenValidationError,
    create_capability_token,
    create_session_token,
    new_capability_id,
    new_session_id,
    validate_capability_token,
    validate_session_token,
)
from lumos.db import repositories


def _agent_key():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    public_key_b64 = base64.b64encode(public_key).decode("ascii")
    return private_key, public_key_b64, compute_kid(public_key_b64)


async def _create_agent_with_key(conn, agent_id: str):
    private_key, public_key_b64, kid = _agent_key()
    await repositories.create_agent(conn, agent_id)
    await repositories.create_agent_key(conn, agent_id, kid, public_key_b64)
    return private_key, public_key_b64, kid


@pytest.mark.asyncio
async def test_valid_auth_flow(conn):
    agent_id = f"agent:{uuid4()}"
    private_key, public_key_b64, kid = await _create_agent_with_key(conn, agent_id)
    nonce_value = f"nonce:{uuid4()}"
    nonce = await repositories.create_auth_nonce(
        conn,
        nonce_value,
        datetime.now(UTC) + timedelta(seconds=60),
    )

    consumed = await repositories.consume_auth_nonce(conn, nonce.nonce)
    assert consumed is not None

    timestamp = int(time.time())
    signature = base64.b64encode(
        private_key.sign(auth_payload(agent_id, kid, nonce.nonce, timestamp))
    ).decode("ascii")
    assert verify_auth_signature(public_key_b64, agent_id, kid, nonce.nonce, timestamp, signature)

    issuer_key = Ed25519PrivateKey.generate()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=10)
    session = await repositories.create_session(
        conn,
        session_id=new_session_id(),
        agent_id=agent_id,
        kid=kid,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    token = create_session_token(
        issuer_key,
        agent_id,
        session.session_id,
        kid,
        issued_at,
        expires_at,
    )

    _, validated = await validate_session_token(conn, issuer_key.public_key(), token)
    assert validated.session_id == session.session_id

    capability_issued_at = datetime.now(UTC)
    capability_expires_at = capability_issued_at + timedelta(minutes=5)
    capability = await repositories.create_capability(
        conn,
        capability_id=new_capability_id(),
        session_id=session.session_id,
        agent_id=agent_id,
        audience="mcp:test",
        tools=["tool.echo"],
        constraints={},
        issued_at=capability_issued_at,
        expires_at=capability_expires_at,
    )
    capability_token = create_capability_token(
        issuer_key,
        agent_id,
        session.session_id,
        capability.capability_id,
        "mcp:test",
        ["tool.echo"],
        {},
        capability_issued_at,
        capability_expires_at,
    )

    _, validated_capability = await validate_capability_token(
        conn,
        issuer_key.public_key(),
        capability_token,
        audience="mcp:test",
    )
    assert validated_capability.capability_id == capability.capability_id


@pytest.mark.asyncio
async def test_replayed_nonce_fails(conn):
    nonce = await repositories.create_auth_nonce(
        conn,
        f"nonce:{uuid4()}",
        datetime.now(UTC) + timedelta(seconds=60),
    )
    assert await repositories.consume_auth_nonce(conn, nonce.nonce) is not None
    assert await repositories.consume_auth_nonce(conn, nonce.nonce) is None


@pytest.mark.asyncio
async def test_revoked_session_fails_validation(conn):
    agent_id = f"agent:{uuid4()}"
    _, _, kid = await _create_agent_with_key(conn, agent_id)
    issuer_key = Ed25519PrivateKey.generate()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=10)
    session = await repositories.create_session(
        conn,
        session_id=new_session_id(),
        agent_id=agent_id,
        kid=kid,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    token = create_session_token(issuer_key, agent_id, session.session_id, kid, issued_at, expires_at)

    await repositories.revoke_session(conn, session.session_id)

    with pytest.raises(TokenValidationError):
        await validate_session_token(conn, issuer_key.public_key(), token)


@pytest.mark.asyncio
async def test_expired_token_fails_validation(conn):
    agent_id = f"agent:{uuid4()}"
    _, _, kid = await _create_agent_with_key(conn, agent_id)
    issuer_key = Ed25519PrivateKey.generate()
    issued_at = datetime.now(UTC) - timedelta(minutes=10)
    expires_at = datetime.now(UTC) - timedelta(minutes=5)
    session = await repositories.create_session(
        conn,
        session_id=new_session_id(),
        agent_id=agent_id,
        kid=kid,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    token = create_session_token(issuer_key, agent_id, session.session_id, kid, issued_at, expires_at)

    with pytest.raises(TokenValidationError):
        await validate_session_token(conn, issuer_key.public_key(), token)


@pytest.mark.asyncio
async def test_transaction_rollback_on_failure(conn):
    agent_id = f"agent:{uuid4()}"
    _, _, kid = await _create_agent_with_key(conn, agent_id)
    session_id = new_session_id()

    try:
        async with conn.transaction():
            await repositories.create_session(
                conn,
                session_id=session_id,
                agent_id=agent_id,
                kid=kid,
                issued_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
            # Simulate a failure inside the transaction
            raise ValueError("simulated failure")
    except ValueError:
        pass

    # Ensure no partial data was written
    session = await repositories.get_session(conn, session_id)
    assert session is None


@pytest.mark.asyncio
async def test_timestamp_tolerance(conn):
    agent_id = f"agent:{uuid4()}"
    _, _, kid = await _create_agent_with_key(conn, agent_id)
    issuer_key = Ed25519PrivateKey.generate()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=10)
    session = await repositories.create_session(
        conn,
        session_id=new_session_id(),
        agent_id=agent_id,
        kid=kid,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    
    # Intentionally offset the timestamp by 1 second (within tolerance)
    offset_issued_at = issued_at - timedelta(seconds=1)
    offset_expires_at = expires_at + timedelta(seconds=1)
    
    token = create_session_token(
        issuer_key, 
        agent_id, 
        session.session_id, 
        kid, 
        offset_issued_at, 
        offset_expires_at
    )

    # Validation should still pass because difference is <= 1
    _, validated = await validate_session_token(conn, issuer_key.public_key(), token)
    assert validated.session_id == session.session_id


@pytest.mark.asyncio
async def test_expired_nonce_cannot_create_session(conn, test_database_url, monkeypatch):
    from fastapi import HTTPException
    from lumos.api.main import app, create_session
    from lumos.api.schemas import SessionCreateRequest
    from lumos.config import settings
    from lumos.db import db

    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()

    agent_id = f"agent:{uuid4()}"
    private_key, _, kid = await _create_agent_with_key(conn, agent_id)
    nonce = await repositories.create_auth_nonce(
        conn,
        f"nonce:{uuid4()}",
        datetime.now(UTC) - timedelta(seconds=1),
    )
    timestamp = int(time.time())
    signature = base64.b64encode(
        private_key.sign(auth_payload(agent_id, kid, nonce.nonce, timestamp))
    ).decode("ascii")
    app.state.issuer_private_key = Ed25519PrivateKey.generate()

    try:
        with pytest.raises(HTTPException) as exc:
            await create_session(
                SessionCreateRequest(
                    agent_id=agent_id,
                    kid=kid,
                    nonce=nonce.nonce,
                    timestamp=timestamp,
                    signature=signature,
                )
            )
    finally:
        await db.close()

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_revoked_key_cannot_create_session(conn, test_database_url, monkeypatch):
    from fastapi import HTTPException
    from lumos.api.main import app, create_session
    from lumos.api.schemas import SessionCreateRequest
    from lumos.config import settings
    from lumos.db import db

    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()

    agent_id = f"agent:{uuid4()}"
    private_key, _, kid = await _create_agent_with_key(conn, agent_id)
    await repositories.revoke_agent_key(conn, agent_id, kid)
    nonce = await repositories.create_auth_nonce(
        conn,
        f"nonce:{uuid4()}",
        datetime.now(UTC) + timedelta(seconds=60),
    )
    timestamp = int(time.time())
    signature = base64.b64encode(
        private_key.sign(auth_payload(agent_id, kid, nonce.nonce, timestamp))
    ).decode("ascii")
    app.state.issuer_private_key = Ed25519PrivateKey.generate()

    try:
        with pytest.raises(HTTPException) as exc:
            await create_session(
                SessionCreateRequest(
                    agent_id=agent_id,
                    kid=kid,
                    nonce=nonce.nonce,
                    timestamp=timestamp,
                    signature=signature,
                )
            )
    finally:
        await db.close()

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_tampered_signature_cannot_create_session(conn, test_database_url, monkeypatch):
    from fastapi import HTTPException
    from lumos.api.main import app, create_session
    from lumos.api.schemas import SessionCreateRequest
    from lumos.config import settings
    from lumos.db import db

    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()

    agent_id = f"agent:{uuid4()}"
    _, _, kid = await _create_agent_with_key(conn, agent_id)
    nonce = await repositories.create_auth_nonce(
        conn,
        f"nonce:{uuid4()}",
        datetime.now(UTC) + timedelta(seconds=60),
    )
    app.state.issuer_private_key = Ed25519PrivateKey.generate()

    try:
        with pytest.raises(HTTPException) as exc:
            await create_session(
                SessionCreateRequest(
                    agent_id=agent_id,
                    kid=kid,
                    nonce=nonce.nonce,
                    timestamp=int(time.time()),
                    signature="not-base64",
                )
            )
    finally:
        await db.close()

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_revocation_metadata(conn):
    agent_id = f"agent:{uuid4()}"
    _, _, kid = await _create_agent_with_key(conn, agent_id)
    session = await repositories.create_session(
        conn,
        session_id=new_session_id(),
        agent_id=agent_id,
        kid=kid,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    
    # Initially revoked_at should be None
    assert session.revoked_at is None
    
    # Revoke session
    revoked_session = await repositories.revoke_session(conn, session.session_id)
    
    # revoked_at should be set
    assert revoked_session.status == "revoked"
    assert revoked_session.revoked_at is not None


@pytest.mark.asyncio
async def test_enforce_endpoint_logic(conn, test_database_url):
    from lumos.api.main import enforce, app
    from lumos.api.schemas import EnforceRequest
    from lumos.db import db
    from lumos.config import settings
    
    settings.database_url = test_database_url
    await db.connect()
    
    try:
        agent_id = f"agent:{uuid4()}"
        _, _, kid = await _create_agent_with_key(conn, agent_id)
        issuer_key = Ed25519PrivateKey.generate()
        app.state.issuer_public_key = issuer_key.public_key()
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(minutes=10)
        
        session = await repositories.create_session(
            conn,
            session_id=new_session_id(),
            agent_id=agent_id,
            kid=kid,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        
        capability = await repositories.create_capability(
            conn,
            capability_id=new_capability_id(),
            session_id=session.session_id,
            agent_id=agent_id,
            audience="mcp:test",
            tools=["tool.allow"],
            constraints={},
            issued_at=issued_at,
            expires_at=expires_at,
        )
        
        token = create_capability_token(
            issuer_key,
            agent_id,
            session.session_id,
            capability.capability_id,
            "mcp:test",
            ["tool.allow"],
            {},
            issued_at,
            expires_at,
        )
        
        # 1. Valid capability -> allowed
        req = EnforceRequest(capability_token=token, audience="mcp:test", tool="tool.allow")
        res = await enforce(req)
        assert res.allowed is True
        
        # 2. Invalid token -> denied
        req_invalid = EnforceRequest(capability_token="invalid", audience="mcp:test")
        res_invalid = await enforce(req_invalid)
        assert res_invalid.allowed is False
        assert res_invalid.reason == "invalid capability"
        
        # 3. Wrong audience -> denied
        req_wrong_aud = EnforceRequest(capability_token=token, audience="mcp:wrong")
        res_wrong_aud = await enforce(req_wrong_aud)
        assert res_wrong_aud.allowed is False
        assert res_wrong_aud.reason == "invalid capability"
        
        # 4. Tool not in capability -> denied
        req_wrong_tool = EnforceRequest(capability_token=token, audience="mcp:test", tool="tool.deny")
        res_wrong_tool = await enforce(req_wrong_tool)
        assert res_wrong_tool.allowed is False
        assert res_wrong_tool.reason == "tool not allowed"
        
        # 5. Revoked capability -> denied
        await repositories.revoke_capability(conn, capability.capability_id)
        req_revoked = EnforceRequest(capability_token=token, audience="mcp:test")
        res_revoked = await enforce(req_revoked)
        assert res_revoked.allowed is False
        assert res_revoked.reason == "invalid capability"
    finally:
        await db.close()

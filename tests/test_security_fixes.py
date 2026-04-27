import base64
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
import os
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import HTTPException

from lumos.api.main import app as api_app
from lumos.api.security import require_admin
from lumos.auth.crypto import compute_kid
from lumos.auth.issuer import load_or_create_issuer_private_key
from lumos.config import settings
from lumos.db import db, repositories
from lumos.db.sweeper import sweep_once
from lumos.proxy.audit import AuditQueue, ProxyAuditEvent


def _agent_key() -> tuple[Ed25519PrivateKey, str, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    public_key_b64 = base64.b64encode(public_key).decode("ascii")
    return private_key, public_key_b64, compute_kid(public_key_b64)


async def _create_agent_with_key(conn, agent_id: str) -> tuple[Ed25519PrivateKey, str]:
    private_key, public_key_b64, kid = _agent_key()
    await repositories.create_agent(conn, agent_id)
    await repositories.create_agent_key(conn, agent_id, kid, public_key_b64)
    return private_key, kid


@asynccontextmanager
async def _api_client(
    test_database_url: str,
    tmp_path,
    monkeypatch,
    admin_token: str = "test-admin-token",
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", test_database_url)
    monkeypatch.setattr(settings, "admin_token", admin_token)
    monkeypatch.setattr(settings, "issuer_key_path", str(tmp_path / "issuer.key"))
    async with api_app.router.lifespan_context(api_app):
        transport = httpx.ASGITransport(app=api_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
            yield client


@pytest.mark.asyncio
async def test_internal_db_init_requires_admin_token(conn, test_database_url, tmp_path, monkeypatch):
    async with _api_client(test_database_url, tmp_path, monkeypatch, admin_token="admin-secret") as client:
        missing = await client.post("/internal/db/init")
        wrong = await client.post(
            "/internal/db/init",
            headers={"Authorization": "Bearer wrong-token"},
        )
        valid = await client.post(
            "/internal/db/init",
            headers={"Authorization": "Bearer admin-secret"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert valid.status_code == 200
    assert valid.json() == {"status": "initialized"}


@pytest.mark.asyncio
async def test_require_admin_rejects_wrong_token(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "expected-token")

    with pytest.raises(HTTPException) as exc:
        await require_admin("Bearer wrong-token")

    assert exc.value.status_code == 401


def test_load_or_create_issuer_private_key_sets_0600_permissions(tmp_path, monkeypatch):
    key_path = tmp_path / "issuer.key"
    monkeypatch.setattr(settings, "issuer_key_path", str(key_path))

    load_or_create_issuer_private_key()

    if os.name == "nt":
        recorded_calls: list[tuple[str, int]] = []

        def record_chmod(path: os.PathLike[str] | str, mode: int) -> None:
            recorded_calls.append((os.fspath(path), mode))

        monkeypatch.setattr("lumos.auth.issuer.os.chmod", record_chmod)
        key_path.unlink()
        load_or_create_issuer_private_key()
        assert recorded_calls == [(str(key_path), 0o600)]
    else:
        assert oct(key_path.stat().st_mode & 0o777) == oct(0o600)


@pytest.mark.asyncio
async def test_sweep_once_deletes_expired_nonce(conn, test_database_url, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()
    nonce = f"nonce:{uuid4()}"
    try:
        await repositories.create_auth_nonce(
            conn,
            nonce,
            datetime.now(UTC) - timedelta(seconds=1),
        )
        await sweep_once()
    finally:
        await db.close()

    assert await conn.fetchval("SELECT nonce FROM auth_nonces WHERE nonce = $1", nonce) is None


@pytest.mark.asyncio
async def test_sweep_once_marks_expired_session(conn, test_database_url, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()
    agent_id = f"agent:{uuid4()}"
    _, kid = await _create_agent_with_key(conn, agent_id)
    session = await repositories.create_session(
        conn,
        session_id=f"session:{uuid4()}",
        agent_id=agent_id,
        kid=kid,
        issued_at=datetime.now(UTC) - timedelta(minutes=2),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    try:
        await sweep_once()
    finally:
        await db.close()

    refreshed = await repositories.get_session(conn, session.session_id)
    assert refreshed is not None
    assert refreshed.status == "expired"


@pytest.mark.asyncio
async def test_sweep_once_marks_expired_capability(conn, test_database_url, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()
    agent_id = f"agent:{uuid4()}"
    _, kid = await _create_agent_with_key(conn, agent_id)
    session = await repositories.create_session(
        conn,
        session_id=f"session:{uuid4()}",
        agent_id=agent_id,
        kid=kid,
        issued_at=datetime.now(UTC) - timedelta(minutes=3),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    capability = await repositories.create_capability(
        conn,
        capability_id=f"capability:{uuid4()}",
        session_id=session.session_id,
        agent_id=agent_id,
        audience="mcp:test",
        tools=["tool.echo"],
        constraints={},
        issued_at=datetime.now(UTC) - timedelta(minutes=2),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    try:
        await sweep_once()
    finally:
        await db.close()

    refreshed = await repositories.get_capability(conn, capability.capability_id)
    assert refreshed is not None
    assert refreshed.status == "expired"


@pytest.mark.asyncio
async def test_audit_queue_stop_drains_all_events(conn, test_database_url, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()
    queue = AuditQueue(maxsize=10)
    queue.start()
    try:
        for index in range(5):
            queue.push(
                ProxyAuditEvent(
                    agent_id=f"agent:{index}",
                    tool="tool.echo",
                    allowed=True,
                    reason=f"event-{index}",
                    timestamp=datetime.now(UTC),
                )
            )
        await queue.stop()
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM audit_events WHERE event_type = 'proxy_request'"
        )
    finally:
        await db.close()

    assert count == 5


@pytest.mark.asyncio
async def test_verify_audit_chain_accepts_clean_chain(conn):
    for index in range(5):
        await repositories.create_audit_event(
            conn,
            event_type=f"event-{index}",
            decision="allow",
            reason="ok",
        )

    valid, reason = await repositories.verify_audit_chain(conn)

    assert valid is True
    assert reason == "ok"


@pytest.mark.asyncio
async def test_verify_audit_chain_rejects_corruption(conn):
    for index in range(3):
        await repositories.create_audit_event(
            conn,
            event_type=f"event-{index}",
            decision="allow",
            reason="ok",
        )

    await conn.execute(
        """
        UPDATE audit_events
        SET event_hash = 'corrupted'
        WHERE id = (
            SELECT id
            FROM audit_events
            ORDER BY timestamp ASC
            OFFSET 1
            LIMIT 1
        )
        """
    )

    valid, reason = await repositories.verify_audit_chain(conn)

    assert valid is False
    assert "Hash mismatch" in reason or "Chain broken" in reason


@pytest.mark.asyncio
async def test_first_audit_event_prev_hash_is_zero_chain(conn):
    await repositories.create_audit_event(
        conn,
        event_type="event-0",
        decision="allow",
        reason="ok",
    )

    prev_hash = await conn.fetchval(
        "SELECT prev_hash FROM audit_events ORDER BY timestamp ASC LIMIT 1"
    )

    assert prev_hash == "0" * 64


@pytest.mark.asyncio
async def test_revoke_agent_endpoint_revokes_agent(conn, test_database_url, tmp_path, monkeypatch):
    agent_id = f"agent:{uuid4()}"
    await repositories.create_agent(conn, agent_id)

    async with _api_client(test_database_url, tmp_path, monkeypatch, admin_token="admin-secret") as client:
        response = await client.post(
            f"/v1/agents/{agent_id}/revoke",
            headers={"Authorization": "Bearer admin-secret"},
        )

    agent = await repositories.get_agent(conn, agent_id)
    assert response.status_code == 200
    assert response.json() == {"status": "revoked", "agent_id": agent_id}
    assert agent is not None
    assert agent.status == "revoked"


@pytest.mark.asyncio
async def test_revoke_agent_endpoint_requires_admin(conn, test_database_url, tmp_path, monkeypatch):
    agent_id = f"agent:{uuid4()}"
    await repositories.create_agent(conn, agent_id)

    async with _api_client(test_database_url, tmp_path, monkeypatch, admin_token="admin-secret") as client:
        response = await client.post(
            f"/v1/agents/{agent_id}/revoke",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_revoke_agent_endpoint_returns_404_for_missing_agent(
    conn,
    test_database_url,
    tmp_path,
    monkeypatch,
):
    async with _api_client(test_database_url, tmp_path, monkeypatch, admin_token="admin-secret") as client:
        response = await client.post(
            f"/v1/agents/agent:{uuid4()}/revoke",
            headers={"Authorization": "Bearer admin-secret"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_revoke_agent_key_endpoint_revokes_key(conn, test_database_url, tmp_path, monkeypatch):
    agent_id = f"agent:{uuid4()}"
    _, kid = await _create_agent_with_key(conn, agent_id)

    async with _api_client(test_database_url, tmp_path, monkeypatch, admin_token="admin-secret") as client:
        response = await client.post(
            f"/v1/agents/{agent_id}/keys/{kid}/revoke",
            headers={"Authorization": "Bearer admin-secret"},
        )

    key = await repositories.get_agent_key(conn, agent_id, kid)
    assert response.status_code == 200
    assert response.json() == {"status": "revoked", "agent_id": agent_id, "kid": kid}
    assert key is not None
    assert key.status == "revoked"


@pytest.mark.asyncio
async def test_revoke_agent_key_endpoint_returns_404_for_missing_key(
    conn,
    test_database_url,
    tmp_path,
    monkeypatch,
):
    agent_id = f"agent:{uuid4()}"
    await repositories.create_agent(conn, agent_id)

    async with _api_client(test_database_url, tmp_path, monkeypatch, admin_token="admin-secret") as client:
        response = await client.post(
            f"/v1/agents/{agent_id}/keys/missing-kid/revoke",
            headers={"Authorization": "Bearer admin-secret"},
        )

    assert response.status_code == 404

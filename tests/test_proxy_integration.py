import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from lumos.config import settings
from lumos.db import db
from lumos.db import repositories
from lumos.auth.crypto import compute_kid
from lumos.auth.tokens import create_capability_token, new_capability_id, new_session_id
from lumos.policy.loader import reload_policy
from lumos.proxy.main import app as proxy_app
from lumos.proxy.router import Router
from lumos.proxy import proxy as proxy_module


@pytest.mark.asyncio
async def test_proxy_end_to_end(conn, test_database_url: str, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)

    config_path = tmp_path / "lumos.config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "proxy:",
                "  audit_queue_size: 1000",
                "routes:",
                "  tool.echo: http://upstream.test/mcp",
                "  '*': http://upstream.test/mcp",
            ]
        ),
        encoding="utf-8",
    )
    issuer_key = Ed25519PrivateKey.generate()
    agent_key = Ed25519PrivateKey.generate()
    public_key_bytes = agent_key.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    import base64

    public_key = base64.b64encode(public_key_bytes).decode("ascii")
    kid = compute_kid(public_key)
    agent_id = "agent:test"
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=10)
    session_id = new_session_id()
    capability_id = new_capability_id()
    audience = "http://upstream.test/mcp"
    await repositories.create_agent(conn, agent_id)
    await repositories.create_agent_key(conn, agent_id, kid, public_key)
    await repositories.create_session(conn, session_id, agent_id, kid, issued_at, expires_at)
    await repositories.create_capability(
        conn,
        capability_id=capability_id,
        session_id=session_id,
        agent_id=agent_id,
        audience=audience,
        tools=["tool.echo"],
        constraints={},
        issued_at=issued_at,
        expires_at=expires_at,
    )
    capability_token = create_capability_token(
        issuer_key,
        agent_id,
        session_id,
        capability_id,
        audience,
        ["tool.echo"],
        {},
        issued_at,
        expires_at,
    )

    upstream_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal upstream_calls
        if str(request.url) == "http://upstream.test/mcp":
            upstream_calls += 1
            payload = json.loads(request.content.decode("utf-8"))
            if payload["method"] == "tools/list":
                return httpx.Response(
                    200,
                    json={"jsonrpc": "2.0", "id": payload.get("id"), "result": {"tools": ["tool.echo"]}},
                )
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "result": {"content": [{"type": "text", "text": "upstream ok"}]},
                },
            )

        return httpx.Response(404, json={"detail": "unexpected request"})

    async with proxy_app.router.lifespan_context(proxy_app):
        await proxy_app.state.http_client.aclose()
        proxy_app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        proxy_app.state.router = Router(config_path)
        proxy_app.state.issuer_public_key = issuer_key.public_key()
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        (policy_dir / "default.yaml").write_text(
            "\n".join(
                [
                    "rules:",
                    '  - name: "allow-echo"',
                    '    tool: "tool.echo"',
                    '    action: "allow"',
                    '  - name: "block-delete"',
                    '    tool: "tool.delete"',
                    '    action: "deny"',
                ]
            ),
            encoding="utf-8",
        )
        reload_policy(policy_dir)

        transport = httpx.ASGITransport(app=proxy_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy.test") as client:
            valid_response = await client.post(
                "/proxy",
                headers={"Authorization": f"Bearer {capability_token}", "x-lumos-agent-id": agent_id},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "tool.echo", "arguments": {"message": "hello"}},
                },
            )
            assert valid_response.status_code == 200
            assert valid_response.json()["result"]["content"][0]["text"] == "upstream ok"

            forged_response = await client.post(
                "/proxy",
                headers={"Authorization": "Bearer forged.token.value", "x-lumos-agent-id": agent_id},
                json={
                    "jsonrpc": "2.0",
                    "id": 20,
                    "method": "tools/call",
                    "params": {"name": "tool.echo", "arguments": {"message": "forged"}},
                },
            )
            assert forged_response.status_code == 200
            assert "access denied" in forged_response.json()["error"]["message"]

            denied_response = await client.post(
                "/proxy",
                headers={"Authorization": f"Bearer {capability_token}", "x-lumos-agent-id": agent_id},
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "tool.delete", "arguments": {"message": "blocked"}},
                },
            )
            assert denied_response.status_code == 200
            assert denied_response.json()["error"]["code"] == -32000
            assert "access denied" in denied_response.json()["error"]["message"]

            list_response = await client.post(
                "/proxy",
                json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            )
            assert list_response.status_code == 200
            assert list_response.json()["result"]["tools"] == ["tool.echo"]

        await proxy_app.state.audit_queue.join()
        async with db.acquire() as audit_conn:
            rows = await audit_conn.fetch(
                """
                SELECT decision, tool_name, reason
                FROM audit_events
                WHERE event_type = 'proxy_request'
                ORDER BY timestamp ASC
                """
            )

    assert upstream_calls == 2
    assert len(rows) == 4
    assert rows[0]["decision"] == "allow"
    assert rows[0]["tool_name"] == "tool.echo"
    assert rows[1]["decision"] == "deny"
    assert rows[2]["decision"] == "deny"
    assert rows[3]["decision"] == "allow"
    assert rows[3]["tool_name"] is None


@pytest.mark.asyncio
async def test_proxy_uses_capability_agent_id_not_spoofed_header(
    conn,
    test_database_url: str,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "database_url", test_database_url)

    config_path = tmp_path / "lumos.config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "proxy:",
                "  audit_queue_size: 1000",
                "routes:",
                "  tool.echo: http://upstream.test/mcp",
            ]
        ),
        encoding="utf-8",
    )
    issuer_key = Ed25519PrivateKey.generate()
    agent_key = Ed25519PrivateKey.generate()
    public_key_bytes = agent_key.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    import base64

    public_key = base64.b64encode(public_key_bytes).decode("ascii")
    kid = compute_kid(public_key)
    real_agent_id = "agent:real"
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=10)
    session_id = new_session_id()
    capability_id = new_capability_id()
    audience = "http://upstream.test/mcp"
    await repositories.create_agent(conn, real_agent_id)
    await repositories.create_agent_key(conn, real_agent_id, kid, public_key)
    await repositories.create_session(conn, session_id, real_agent_id, kid, issued_at, expires_at)
    await repositories.create_capability(
        conn,
        capability_id=capability_id,
        session_id=session_id,
        agent_id=real_agent_id,
        audience=audience,
        tools=["tool.echo"],
        constraints={},
        issued_at=issued_at,
        expires_at=expires_at,
    )
    capability_token = create_capability_token(
        issuer_key,
        real_agent_id,
        session_id,
        capability_id,
        audience,
        ["tool.echo"],
        {},
        issued_at,
        expires_at,
    )

    seen_agent_ids: list[str] = []

    async def record_evaluate(ctx):
        seen_agent_ids.append(ctx["agent_id"])
        return SimpleNamespace(action="allow", reason=None, rule_name="allow")

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": payload.get("id"), "result": {"ok": True}},
        )

    monkeypatch.setattr(proxy_module.policy_engine, "evaluate", record_evaluate)

    async with proxy_app.router.lifespan_context(proxy_app):
        await proxy_app.state.http_client.aclose()
        proxy_app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        proxy_app.state.router = Router(config_path)
        proxy_app.state.issuer_public_key = issuer_key.public_key()

        transport = httpx.ASGITransport(app=proxy_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy.test") as client:
            response = await client.post(
                "/proxy",
                headers={
                    "Authorization": f"Bearer {capability_token}",
                    "x-lumos-agent-id": "agent:spoofed",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 99,
                    "method": "tools/call",
                    "params": {"name": "tool.echo", "arguments": {"message": "hello"}},
                },
            )

    assert response.status_code == 200
    assert response.json()["result"]["ok"] is True
    assert seen_agent_ids == [real_agent_id]

import base64
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from lumos.api.main import app
from lumos.auth.crypto import compute_kid
from lumos.db import repositories
from lumos.policy.loader import reload_policy
from lumos.config import settings


ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


def _policy_text() -> str:
    return "\n".join(
        [
            "rules:",
            '  - name: "allow-all"',
            '    tool: "*"',
            '    action: "allow"',
        ]
    )


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
    await repositories.create_agent(conn, agent_id, display_name=f"Display {agent_id}")
    await repositories.create_agent_key(conn, agent_id, kid, public_key_b64)
    return private_key, kid


@asynccontextmanager
async def _client_context(test_database_url: str, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)
    monkeypatch.setattr(settings, "admin_token", "test-admin-token")
    monkeypatch.setattr(settings, "issuer_key_path", str(tmp_path / "issuer.key"))
    monkeypatch.chdir(tmp_path)
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir(exist_ok=True)
    (policy_dir / "default.yaml").write_text(_policy_text(), encoding="utf-8")
    reload_policy(policy_dir)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c


@pytest_asyncio.fixture
async def client(conn, test_database_url, tmp_path, monkeypatch):
    async with _client_context(test_database_url, tmp_path, monkeypatch) as c:
        yield c


@pytest.mark.asyncio
async def test_list_events_empty_returns_empty_list(client):
    response = await client.get("/api/events", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["events"] == []
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_events_returns_created_events(client, conn):
    await repositories.create_audit_event(conn, event_type="one", decision="allow", reason="ok")
    await repositories.create_audit_event(conn, event_type="two", decision="deny", reason="blocked")

    response = await client.get("/api/events", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert {event["event_type"] for event in response.json()["events"]} == {"one", "two"}
    assert all("event_hash" in event for event in response.json()["events"])
    assert all("metadata" not in event for event in response.json()["events"])


@pytest.mark.asyncio
async def test_list_events_filter_by_agent_id(client, conn):
    await repositories.create_agent(conn, "agent:one")
    await repositories.create_agent(conn, "agent:two")
    await repositories.create_audit_event(conn, event_type="one", decision="allow", agent_id="agent:one")
    await repositories.create_audit_event(conn, event_type="two", decision="deny", agent_id="agent:two")

    response = await client.get("/api/events?agent_id=agent:one", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["events"][0]["agent_id"] == "agent:one"


@pytest.mark.asyncio
async def test_list_events_filter_by_decision(client, conn):
    await repositories.create_audit_event(conn, event_type="one", decision="allow")
    await repositories.create_audit_event(conn, event_type="two", decision="deny")

    response = await client.get("/api/events?decision=deny", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["events"][0]["decision"] == "deny"


@pytest.mark.asyncio
async def test_list_events_filter_by_since(client, conn):
    await repositories.create_audit_event(
        conn,
        event_type="old",
        decision="allow",
    )
    since = datetime.now(UTC)
    await repositories.create_audit_event(
        conn,
        event_type="new",
        decision="allow",
    )

    response = await client.get("/api/events", headers=ADMIN_HEADERS, params={"since": since.isoformat()})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["events"][0]["event_type"] == "new"


@pytest.mark.asyncio
async def test_list_events_pagination_limit_offset(client, conn):
    for index in range(3):
        await repositories.create_audit_event(conn, event_type=f"event-{index}", decision="allow")

    response = await client.get("/api/events?limit=1&offset=1", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 1
    assert len(response.json()["events"]) == 1
    assert response.json()["total"] == 3


@pytest.mark.asyncio
async def test_list_events_limit_capped_at_200(client):
    response = await client.get("/api/events?limit=201", headers=ADMIN_HEADERS)

    assert response.status_code == 422
    assert "error" in response.json()


@pytest.mark.asyncio
async def test_get_event_by_id_returns_event(client, conn):
    event = await repositories.create_audit_event(conn, event_type="lookup", decision="allow", reason="ok")

    response = await client.get(f"/api/events/{event.id}", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["id"] == str(event.id)
    assert response.json()["event_type"] == "lookup"


@pytest.mark.asyncio
async def test_get_event_by_id_404_for_missing(client):
    response = await client.get(
        f"/api/events/{uuid4()}",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 404
    assert response.json() == {"error": "event not found"}


@pytest.mark.asyncio
async def test_list_events_requires_admin(client):
    response = await client.get("/api/events")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_agents_returns_agents_with_stats(client, conn):
    await repositories.create_agent(conn, "agent:one", "One")
    await repositories.create_agent(conn, "agent:two", "Two")
    await repositories.create_audit_event(conn, event_type="proxy_request", decision="allow", agent_id="agent:one")
    await repositories.create_audit_event(conn, event_type="proxy_request", decision="deny", agent_id="agent:one")

    response = await client.get("/api/agents", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["total"] == 2
    agent = next(item for item in response.json()["agents"] if item["agent_id"] == "agent:one")
    assert agent["stats"]["total_calls"] == 2
    assert agent["stats"]["allowed_calls"] == 1
    assert agent["stats"]["denied_calls"] == 1


@pytest.mark.asyncio
async def test_list_agents_filter_by_status(client, conn):
    await repositories.create_agent(conn, "agent:active")
    await repositories.create_agent(conn, "agent:revoked")
    await repositories.revoke_agent(conn, "agent:revoked")

    response = await client.get("/api/agents?status=revoked", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["agents"][0]["agent_id"] == "agent:revoked"


@pytest.mark.asyncio
async def test_get_agent_returns_stats(client, conn):
    await repositories.create_agent(conn, "agent:stats", "Stats")
    await repositories.create_audit_event(conn, event_type="proxy_request", decision="allow", agent_id="agent:stats")

    response = await client.get("/api/agents/agent:stats", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["agent_id"] == "agent:stats"
    assert response.json()["stats"]["allowed_calls"] == 1


@pytest.mark.asyncio
async def test_get_agent_404_for_missing(client):
    response = await client.get("/api/agents/missing", headers=ADMIN_HEADERS)

    assert response.status_code == 404
    assert response.json() == {"error": "agent not found"}


@pytest.mark.asyncio
async def test_list_agents_requires_admin(client):
    response = await client.get("/api/agents")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_summary_stats_returns_correct_counts(client, conn):
    _, kid = await _create_agent_with_key(conn, "agent:summary")
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=10)
    session = await repositories.create_session(
        conn,
        session_id=f"session:{uuid4()}",
        agent_id="agent:summary",
        kid=kid,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    await repositories.create_capability(
        conn,
        capability_id=f"capability:{uuid4()}",
        session_id=session.session_id,
        agent_id="agent:summary",
        audience="mcp:test",
        tools=["tool.echo"],
        constraints={},
        issued_at=issued_at,
        expires_at=expires_at,
    )
    await repositories.create_audit_event(conn, event_type="proxy_request", decision="allow", agent_id="agent:summary")
    await repositories.create_audit_event(conn, event_type="proxy_request", decision="deny", agent_id="agent:summary")

    response = await client.get("/api/stats/summary", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_agents"] == 1
    assert payload["active_agents"] == 1
    assert payload["total_calls_today"] == 2
    assert payload["allowed_calls_today"] == 1
    assert payload["denied_calls_today"] == 1
    assert payload["total_calls_all_time"] == 2
    assert payload["active_sessions"] == 1
    assert payload["active_capabilities"] == 1
    assert payload["audit_chain_verified"] is True


@pytest.mark.asyncio
async def test_summary_stats_today_counts_zero_on_empty(client):
    response = await client.get("/api/stats/summary", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["total_calls_today"] == 0
    assert response.json()["allowed_calls_today"] == 0
    assert response.json()["denied_calls_today"] == 0


@pytest.mark.asyncio
async def test_costs_returns_budget_state(client, conn):
    await conn.execute(
        "INSERT INTO budget_state (agent_id, period, usage) VALUES ($1, $2, $3)",
        "agent:cost",
        "2026-04-27",
        3,
    )
    policy_dir = Path("policies")
    (policy_dir / "default.yaml").write_text(
        "\n".join(
            [
                "budgets:",
                '  "agent:cost":',
                '    period: "daily"',
                "    limit: 5",
                "    default_cost: 1",
            ]
        ),
        encoding="utf-8",
    )
    reload_policy(policy_dir)

    response = await client.get("/api/stats/costs", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["agents"] == [
        {"agent_id": "agent:cost", "period": "2026-04-27", "usage": 3, "limit": 5}
    ]


@pytest.mark.asyncio
async def test_summary_stats_requires_admin(client):
    response = await client.get("/api/stats/summary")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_policy_returns_current_policy(client):
    response = await client.get("/api/policy", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert "policy" in response.json()
    assert "policy_dir" in response.json()
    assert "fingerprint" in response.json()


@pytest.mark.asyncio
async def test_validate_policy_accepts_valid_yaml(client):
    response = await client.post(
        "/api/policy/validate",
        headers=ADMIN_HEADERS,
        json={"yaml_content": _policy_text()},
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "error": None}


@pytest.mark.asyncio
async def test_validate_policy_rejects_invalid_yaml(client):
    response = await client.post(
        "/api/policy/validate",
        headers=ADMIN_HEADERS,
        json={"yaml_content": "rules: ["},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["error"] is not None


@pytest.mark.asyncio
async def test_put_policy_applies_valid_yaml(client):
    yaml_content = "\n".join(
        [
            "rules:",
            '  - name: "deny-delete"',
            '    tool: "tool.delete"',
            '    action: "deny"',
        ]
    )

    response = await client.put(
        "/api/policy",
        headers=ADMIN_HEADERS,
        json={"yaml_content": yaml_content},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "applied"}
    saved = (Path("policies") / "default.yaml").read_text(encoding="utf-8")
    assert saved == yaml_content


@pytest.mark.asyncio
async def test_put_policy_rejects_invalid_yaml_with_400(client):
    response = await client.put(
        "/api/policy",
        headers=ADMIN_HEADERS,
        json={"yaml_content": "rules: ["},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid policy"
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_policy_requires_admin(client):
    response = await client.get("/api/policy")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_sessions_returns_sessions(client, conn):
    _, kid = await _create_agent_with_key(conn, "agent:sessions")
    first = await repositories.create_session(
        conn,
        session_id=f"session:{uuid4()}",
        agent_id="agent:sessions",
        kid=kid,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    await repositories.create_session(
        conn,
        session_id=f"session:{uuid4()}",
        agent_id="agent:sessions",
        kid=kid,
        issued_at=datetime.now(UTC) + timedelta(seconds=1),
        expires_at=datetime.now(UTC) + timedelta(minutes=11),
    )

    response = await client.get("/api/sessions", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert any(session["session_id"] == first.session_id for session in response.json()["sessions"])


@pytest.mark.asyncio
async def test_list_sessions_filter_by_status(client, conn):
    _, kid = await _create_agent_with_key(conn, "agent:session-status")
    active = await repositories.create_session(
        conn,
        session_id=f"session:{uuid4()}",
        agent_id="agent:session-status",
        kid=kid,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    await repositories.create_session(
        conn,
        session_id=f"session:{uuid4()}",
        agent_id="agent:session-status",
        kid=kid,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    await repositories.revoke_session(conn, active.session_id)

    response = await client.get("/api/sessions?status=revoked", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["sessions"][0]["status"] == "revoked"


@pytest.mark.asyncio
async def test_get_session_by_id_returns_session(client, conn):
    _, kid = await _create_agent_with_key(conn, "agent:get-session")
    session = await repositories.create_session(
        conn,
        session_id=f"session:{uuid4()}",
        agent_id="agent:get-session",
        kid=kid,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    response = await client.get(f"/api/sessions/{session.session_id}", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["session_id"] == session.session_id
    assert response.json()["agent_id"] == "agent:get-session"


@pytest.mark.asyncio
async def test_get_session_by_id_404_for_missing(client):
    response = await client.get("/api/sessions/missing", headers=ADMIN_HEADERS)

    assert response.status_code == 404
    assert response.json() == {"error": "session not found"}


@pytest.mark.asyncio
async def test_list_sessions_requires_admin(client):
    response = await client.get("/api/sessions")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_audit_chain_verify_returns_valid_on_clean_chain(client, conn):
    for index in range(3):
        await repositories.create_audit_event(conn, event_type=f"event-{index}", decision="allow")

    response = await client.get("/api/audit/verify", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["reason"] == "ok"
    assert response.json()["events_checked"] == 3


@pytest.mark.asyncio
async def test_audit_chain_verify_with_limit_parameter(client, conn):
    for index in range(5):
        await repositories.create_audit_event(conn, event_type=f"event-{index}", decision="allow")

    response = await client.get("/api/audit/verify?limit=2", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["events_checked"] == 2


@pytest.mark.asyncio
async def test_audit_chain_verify_requires_admin(client):
    response = await client.get("/api/audit/verify")

    assert response.status_code == 401

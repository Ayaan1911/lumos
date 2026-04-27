from datetime import UTC, datetime, timedelta
import hashlib
import json
from typing import Any

import asyncpg

from lumos.db.models import Agent, AgentKey, AuditEvent, AuthNonce, Capability, Session


def _agent(row: asyncpg.Record) -> Agent:
    return Agent(**dict(row))


def _agent_key(row: asyncpg.Record) -> AgentKey:
    return AgentKey(**dict(row))


def _session(row: asyncpg.Record) -> Session:
    return Session(**dict(row))


def _capability(row: asyncpg.Record) -> Capability:
    data = dict(row)
    return Capability(**data)


def _audit_event(row: asyncpg.Record) -> AuditEvent:
    data = dict(row)
    data.setdefault("metadata", {})
    return AuditEvent(**data)


def _auth_nonce(row: asyncpg.Record) -> AuthNonce:
    return AuthNonce(**dict(row))


async def _compute_event_hash(event_data: dict, prev_hash: str) -> str:
    payload = json.dumps(event_data, sort_keys=True, default=str)
    raw = (payload + prev_hash).encode()
    return hashlib.sha256(raw).hexdigest()


async def _get_prev_event(conn: asyncpg.Connection) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT event_hash, timestamp FROM audit_events ORDER BY timestamp DESC LIMIT 1"
    )


async def create_agent(
    conn: asyncpg.Connection,
    agent_id: str,
    display_name: str | None = None,
) -> Agent:
    row = await conn.fetchrow(
        """
        INSERT INTO agents (agent_id, display_name)
        VALUES ($1, $2)
        RETURNING *
        """,
        agent_id,
        display_name,
    )
    return _agent(row)


async def get_agent(conn: asyncpg.Connection, agent_id: str) -> Agent | None:
    row = await conn.fetchrow(
        "SELECT * FROM agents WHERE agent_id = $1",
        agent_id,
    )
    return _agent(row) if row else None


async def revoke_agent(conn: asyncpg.Connection, agent_id: str) -> Agent | None:
    row = await conn.fetchrow(
        """
        UPDATE agents
        SET status = 'revoked', revoked_at = NOW()
        WHERE agent_id = $1
        RETURNING *
        """,
        agent_id,
    )
    return _agent(row) if row else None


async def create_agent_key(
    conn: asyncpg.Connection,
    agent_id: str,
    kid: str,
    public_key: str,
) -> AgentKey:
    row = await conn.fetchrow(
        """
        INSERT INTO agent_keys (agent_id, kid, public_key)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        agent_id,
        kid,
        public_key,
    )
    return _agent_key(row)


async def revoke_agent_key(
    conn: asyncpg.Connection,
    agent_id: str,
    kid: str,
) -> AgentKey | None:
    row = await conn.fetchrow(
        """
        UPDATE agent_keys
        SET status = 'revoked', revoked_at = NOW()
        WHERE agent_id = $1 AND kid = $2
        RETURNING *
        """,
        agent_id,
        kid,
    )
    return _agent_key(row) if row else None


async def get_agent_key(
    conn: asyncpg.Connection,
    agent_id: str,
    kid: str,
) -> AgentKey | None:
    row = await conn.fetchrow(
        """
        SELECT * FROM agent_keys
        WHERE agent_id = $1 AND kid = $2
        """,
        agent_id,
        kid,
    )
    return _agent_key(row) if row else None


async def create_auth_nonce(
    conn: asyncpg.Connection,
    nonce: str,
    expires_at: datetime,
) -> AuthNonce:
    row = await conn.fetchrow(
        """
        INSERT INTO auth_nonces (nonce, expires_at)
        VALUES ($1, $2)
        RETURNING *
        """,
        nonce,
        expires_at,
    )
    return _auth_nonce(row)


async def consume_auth_nonce(
    conn: asyncpg.Connection,
    nonce: str,
) -> AuthNonce | None:
    row = await conn.fetchrow(
        """
        UPDATE auth_nonces
        SET consumed_at = NOW()
        WHERE nonce = $1 AND consumed_at IS NULL AND expires_at > NOW()
        RETURNING *
        """,
        nonce,
    )
    return _auth_nonce(row) if row else None


async def create_session(
    conn: asyncpg.Connection,
    session_id: str,
    agent_id: str,
    kid: str,
    issued_at: datetime,
    expires_at: datetime,
    parent_session_id: str | None = None,
) -> Session:
    row = await conn.fetchrow(
        """
        INSERT INTO sessions (session_id, agent_id, kid, parent_session_id, issued_at, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        session_id,
        agent_id,
        kid,
        parent_session_id,
        issued_at,
        expires_at,
    )
    return _session(row)


async def get_session(conn: asyncpg.Connection, session_id: str) -> Session | None:
    row = await conn.fetchrow(
        "SELECT * FROM sessions WHERE session_id = $1",
        session_id,
    )
    return _session(row) if row else None


async def revoke_session(conn: asyncpg.Connection, session_id: str) -> Session | None:
    row = await conn.fetchrow(
        """
        UPDATE sessions
        SET status = 'revoked', revoked_at = NOW()
        WHERE session_id = $1
        RETURNING *
        """,
        session_id,
    )
    return _session(row) if row else None


async def create_capability(
    conn: asyncpg.Connection,
    capability_id: str,
    session_id: str,
    agent_id: str,
    audience: str,
    tools: list[str],
    constraints: dict[str, Any],
    issued_at: datetime,
    expires_at: datetime,
) -> Capability:
    row = await conn.fetchrow(
        """
        INSERT INTO capabilities (
          capability_id, session_id, agent_id, audience, tools, constraints, issued_at, expires_at
        )
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8)
        RETURNING *
        """,
        capability_id,
        session_id,
        agent_id,
        audience,
        tools,
        constraints,
        issued_at,
        expires_at,
    )
    return _capability(row)


async def get_capability(
    conn: asyncpg.Connection,
    capability_id: str,
) -> Capability | None:
    row = await conn.fetchrow(
        "SELECT * FROM capabilities WHERE capability_id = $1",
        capability_id,
    )
    return _capability(row) if row else None


async def revoke_capability(
    conn: asyncpg.Connection,
    capability_id: str,
) -> Capability | None:
    row = await conn.fetchrow(
        """
        UPDATE capabilities
        SET status = 'revoked', revoked_at = NOW()
        WHERE capability_id = $1
        RETURNING *
        """,
        capability_id,
    )
    return _capability(row) if row else None


async def create_audit_event(
    conn: asyncpg.Connection,
    event_type: str,
    decision: str,
    agent_id: str | None = None,
    session_id: str | None = None,
    capability_id: str | None = None,
    audience: str | None = None,
    tool_name: str | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(1234567890)")
        prev_event = await _get_prev_event(conn)
        prev_hash = prev_event["event_hash"] if prev_event and prev_event["event_hash"] else "0" * 64
        timestamp = datetime.now(UTC)
        if prev_event and prev_event["timestamp"] and timestamp <= prev_event["timestamp"]:
            timestamp = prev_event["timestamp"] + timedelta(microseconds=1)
        event_data = {
            "event_type": event_type,
            "agent_id": agent_id,
            "session_id": session_id,
            "capability_id": capability_id,
            "tool_name": tool_name,
            "decision": decision,
            "reason": reason,
            "timestamp": timestamp.isoformat() if timestamp else None,
        }
        event_hash = await _compute_event_hash(event_data, prev_hash)
        row = await conn.fetchrow(
            """
            INSERT INTO audit_events (
              timestamp, event_type, agent_id, session_id, capability_id, audience,
              tool_name, decision, reason, metadata, event_hash, prev_hash
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12)
            RETURNING *
            """,
            timestamp,
            event_type,
            agent_id,
            session_id,
            capability_id,
            audience,
            tool_name,
            decision,
            reason,
            metadata or {},
            event_hash,
            prev_hash,
        )
        return _audit_event(row)


async def verify_audit_chain(conn: asyncpg.Connection, limit: int = 1000) -> tuple[bool, str]:
    rows = await conn.fetch(
        """
        SELECT *
        FROM audit_events
        WHERE event_hash IS NOT NULL
        ORDER BY timestamp ASC
        LIMIT $1
        """,
        limit,
    )
    if not rows:
        return True, "ok"
    for index, row in enumerate(rows):
        expected_prev = "0" * 64 if index == 0 else rows[index - 1]["event_hash"]
        if row["prev_hash"] != expected_prev:
            return False, f"Chain broken at event {row['id']}"
        event_data = {
            "event_type": row["event_type"],
            "agent_id": row["agent_id"],
            "session_id": row["session_id"],
            "capability_id": row["capability_id"],
            "tool_name": row["tool_name"],
            "decision": row["decision"],
            "reason": row["reason"],
            "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
        }
        recomputed = await _compute_event_hash(event_data, row["prev_hash"])
        if recomputed != row["event_hash"]:
            return False, f"Hash mismatch at event {row['id']}"
    return True, "ok"


async def list_audit_events(
    conn: asyncpg.Connection,
    agent_id: str | None = None,
    tool_name: str | None = None,
    decision: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditEvent], int]:
    conditions: list[str] = []
    params: list[Any] = []

    for value, clause in (
        (agent_id, "agent_id = ${index}"),
        (tool_name, "tool_name = ${index}"),
        (decision, "decision = ${index}"),
        (since, "timestamp >= ${index}"),
        (until, "timestamp <= ${index}"),
    ):
        if value is not None:
            params.append(value)
            conditions.append(clause.replace("${index}", f"${len(params)}"))

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    count_row = await conn.fetchrow(
        f"SELECT COUNT(*) AS total FROM audit_events {where_sql}",
        *params,
    )

    query_params = [*params, limit, offset]
    rows = await conn.fetch(
        f"""
        SELECT id, timestamp, event_type, agent_id, session_id, capability_id,
               audience, tool_name, decision, reason, event_hash, prev_hash
        FROM audit_events
        {where_sql}
        ORDER BY timestamp DESC
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """,
        *query_params,
    )
    return [_audit_event(row) for row in rows], int(count_row["total"])


async def get_audit_event(conn: asyncpg.Connection, event_id: str) -> AuditEvent | None:
    row = await conn.fetchrow(
        """
        SELECT id, timestamp, event_type, agent_id, session_id, capability_id,
               audience, tool_name, decision, reason, event_hash, prev_hash
        FROM audit_events
        WHERE id = $1::uuid
        """,
        event_id,
    )
    return _audit_event(row) if row else None


async def list_agents_with_stats(
    conn: asyncpg.Connection,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    rows = await conn.fetch(
        """
        SELECT
            a.agent_id,
            a.display_name,
            a.status,
            a.created_at,
            a.revoked_at,
            COUNT(ae.id) FILTER (
                WHERE ae.decision IN ('allow', 'deny')
            ) AS total_calls,
            COUNT(ae.id) FILTER (
                WHERE ae.decision = 'allow'
            ) AS allowed_calls,
            COUNT(ae.id) FILTER (
                WHERE ae.decision = 'deny'
            ) AS denied_calls,
            MAX(ae.timestamp) FILTER (
                WHERE ae.decision IN ('allow', 'deny')
            ) AS last_seen
        FROM agents a
        LEFT JOIN audit_events ae ON ae.agent_id = a.agent_id
        WHERE ($1::text IS NULL OR a.status = $1)
        GROUP BY a.id, a.agent_id, a.display_name,
                 a.status, a.created_at, a.revoked_at
        ORDER BY a.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        status,
        limit,
        offset,
    )
    count_row = await conn.fetchrow(
        "SELECT COUNT(*) AS total FROM agents WHERE ($1::text IS NULL OR status = $1)",
        status,
    )
    return [dict(row) for row in rows], int(count_row["total"])


async def get_agent_with_stats(conn: asyncpg.Connection, agent_id: str) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT
            a.agent_id,
            a.display_name,
            a.status,
            a.created_at,
            a.revoked_at,
            COUNT(ae.id) FILTER (
                WHERE ae.decision IN ('allow', 'deny')
            ) AS total_calls,
            COUNT(ae.id) FILTER (
                WHERE ae.decision = 'allow'
            ) AS allowed_calls,
            COUNT(ae.id) FILTER (
                WHERE ae.decision = 'deny'
            ) AS denied_calls,
            MAX(ae.timestamp) FILTER (
                WHERE ae.decision IN ('allow', 'deny')
            ) AS last_seen
        FROM agents a
        LEFT JOIN audit_events ae ON ae.agent_id = a.agent_id
        WHERE a.agent_id = $1
        GROUP BY a.id, a.agent_id, a.display_name,
                 a.status, a.created_at, a.revoked_at
        """,
        agent_id,
    )
    return dict(row) if row else None


async def get_summary_stats(conn: asyncpg.Connection) -> dict:
    agents_row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total_agents,
            COUNT(*) FILTER (WHERE status = 'active') AS active_agents
        FROM agents
        """
    )
    calls_row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE decision IN ('allow','deny')
                AND timestamp >= DATE_TRUNC('day', NOW())
            ) AS total_calls_today,
            COUNT(*) FILTER (
                WHERE decision = 'allow'
                AND timestamp >= DATE_TRUNC('day', NOW())
            ) AS allowed_calls_today,
            COUNT(*) FILTER (
                WHERE decision = 'deny'
                AND timestamp >= DATE_TRUNC('day', NOW())
            ) AS denied_calls_today,
            COUNT(*) FILTER (
                WHERE decision IN ('allow','deny')
            ) AS total_calls_all_time
        FROM audit_events
        """
    )
    sessions_row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS active_sessions
        FROM sessions
        WHERE status = 'active' AND expires_at > NOW()
        """
    )
    capabilities_row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS active_capabilities
        FROM capabilities
        WHERE status = 'active' AND expires_at > NOW()
        """
    )
    return {
        "total_agents": int(agents_row["total_agents"]),
        "active_agents": int(agents_row["active_agents"]),
        "total_calls_today": int(calls_row["total_calls_today"]),
        "allowed_calls_today": int(calls_row["allowed_calls_today"]),
        "denied_calls_today": int(calls_row["denied_calls_today"]),
        "total_calls_all_time": int(calls_row["total_calls_all_time"]),
        "active_sessions": int(sessions_row["active_sessions"]),
        "active_capabilities": int(capabilities_row["active_capabilities"]),
    }


async def list_sessions(
    conn: asyncpg.Connection,
    agent_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Session], int]:
    conditions: list[str] = []
    params: list[Any] = []

    for value, clause in (
        (agent_id, "agent_id = ${index}"),
        (status, "status = ${index}"),
    ):
        if value is not None:
            params.append(value)
            conditions.append(clause.replace("${index}", f"${len(params)}"))

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    count_row = await conn.fetchrow(
        f"SELECT COUNT(*) AS total FROM sessions {where_sql}",
        *params,
    )
    rows = await conn.fetch(
        f"""
        SELECT *
        FROM sessions
        {where_sql}
        ORDER BY issued_at DESC
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """,
        *params,
        limit,
        offset,
    )
    return [_session(row) for row in rows], int(count_row["total"])


async def get_budget_state(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT agent_id, period, usage
        FROM budget_state
        ORDER BY agent_id, period
        """
    )
    return [dict(row) for row in rows]

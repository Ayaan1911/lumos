from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Agent:
    id: UUID
    agent_id: str
    display_name: str | None
    status: str
    created_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class AgentKey:
    id: UUID
    agent_id: str
    kid: str
    public_key: str
    status: str
    created_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class Session:
    id: UUID
    session_id: str
    agent_id: str
    kid: str
    parent_session_id: str | None
    issued_at: datetime
    expires_at: datetime
    status: str
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class Capability:
    id: UUID
    capability_id: str
    session_id: str
    agent_id: str
    audience: str
    tools: list[str]
    constraints: dict[str, Any]
    issued_at: datetime
    expires_at: datetime
    status: str
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class AuditEvent:
    id: UUID
    timestamp: datetime
    event_type: str
    agent_id: str | None
    session_id: str | None
    capability_id: str | None
    audience: str | None
    tool_name: str | None
    decision: str
    reason: str | None
    metadata: dict[str, Any]
    event_hash: str | None = None
    prev_hash: str | None = None


@dataclass(frozen=True)
class AuthNonce:
    nonce: str
    expires_at: datetime
    consumed_at: datetime | None

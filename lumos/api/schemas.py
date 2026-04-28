from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentCreateRequest(BaseModel):
    agent_id: str
    display_name: str | None = None


class AgentResponse(BaseModel):
    agent_id: str
    display_name: str | None
    status: str


class AgentKeyCreateRequest(BaseModel):
    public_key: str


class AgentKeyResponse(BaseModel):
    agent_id: str
    kid: str
    public_key: str
    status: str


class NonceResponse(BaseModel):
    nonce: str
    expires_at: datetime


class SessionCreateRequest(BaseModel):
    agent_id: str
    kid: str
    nonce: str
    timestamp: int
    signature: str


class SessionResponse(BaseModel):
    session_id: str
    token: str | None = None
    expires_at: datetime
    agent_id: str | None = None
    kid: str | None = None
    issued_at: datetime | None = None
    status: str | None = None
    revoked_at: datetime | None = None
    parent_session_id: str | None = None


class CapabilityCreateRequest(BaseModel):
    audience: str
    tools: list[str] = Field(min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)


class CapabilityResponse(BaseModel):
    capability_id: str
    token: str
    expires_at: datetime


class EnforceRequest(BaseModel):
    capability_token: str
    audience: str
    tool: str | None = None


class EnforceResponse(BaseModel):
    allowed: bool
    reason: str | None = None


class AuditEventResponse(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    agent_id: str | None = None
    session_id: str | None = None
    capability_id: str | None = None
    audience: str | None = None
    tool_name: str | None = None
    decision: str
    reason: str | None = None
    event_hash: str | None = None
    prev_hash: str | None = None


class AuditEventListResponse(BaseModel):
    events: list[AuditEventResponse]
    total: int
    limit: int
    offset: int


class AgentStats(BaseModel):
    total_calls: int
    allowed_calls: int
    denied_calls: int
    last_seen: datetime | None = None


class AgentWithStatsResponse(BaseModel):
    agent_id: str
    display_name: str | None = None
    status: str
    created_at: datetime
    revoked_at: datetime | None = None
    stats: AgentStats


class AgentListResponse(BaseModel):
    agents: list[AgentWithStatsResponse]
    total: int
    limit: int
    offset: int


class SummaryStatsResponse(BaseModel):
    total_agents: int
    active_agents: int
    total_calls_today: int
    allowed_calls_today: int
    denied_calls_today: int
    total_calls_all_time: int
    active_sessions: int
    active_capabilities: int
    audit_chain_verified: bool


class CostEntry(BaseModel):
    agent_id: str
    period: str
    usage: int
    limit: int | None = None


class CostsResponse(BaseModel):
    agents: list[CostEntry]


class PolicyResponse(BaseModel):
    policy: dict
    policy_dir: str
    fingerprint: dict
    yaml_content: str


class PolicyUpdateRequest(BaseModel):
    yaml_content: str


class PolicyValidateRequest(BaseModel):
    yaml_content: str


class PolicyValidateResponse(BaseModel):
    valid: bool
    error: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int
    limit: int
    offset: int


class AuditChainVerifyResponse(BaseModel):
    valid: bool
    reason: str
    events_checked: int

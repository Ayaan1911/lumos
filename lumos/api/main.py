from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
import secrets
import time

from asyncpg import UniqueViolationError
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import yaml

from lumos.api.schemas import (
    AgentCreateRequest,
    AgentListResponse,
    AgentKeyCreateRequest,
    AgentKeyResponse,
    AgentResponse,
    AgentStats,
    AgentWithStatsResponse,
    AuditChainVerifyResponse,
    AuditEventListResponse,
    AuditEventResponse,
    CapabilityCreateRequest,
    CapabilityResponse,
    CostEntry,
    CostsResponse,
    NonceResponse,
    PolicyResponse,
    PolicyUpdateRequest,
    PolicyValidateRequest,
    PolicyValidateResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
    SummaryStatsResponse,
    EnforceRequest,
    EnforceResponse,
)
from lumos.api.security import require_admin, session_token_from_header
from lumos.auth.crypto import compute_kid, verify_auth_signature
from lumos.auth.issuer import load_or_create_issuer_private_key, public_key_for
from lumos.auth.tokens import (
    TokenValidationError,
    create_capability_token,
    create_session_token,
    default_capability_expiry,
    default_session_expiry,
    new_capability_id,
    new_session_id,
    now_utc,
    validate_capability_token,
    validate_session_token,
)
from lumos.config import settings
from lumos.db import db
from lumos.db import repositories
from lumos.db.sweeper import start_sweeper, stop_sweeper
from lumos.policy.loader import (
    _validate_policy,
    get_policy,
    get_policy_dir,
    get_policy_fingerprint,
    reload_policy,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.connect()
    issuer_private_key = load_or_create_issuer_private_key()
    app.state.issuer_private_key = issuer_private_key
    app.state.issuer_public_key = public_key_for(issuer_private_key)
    start_sweeper()
    try:
        yield
    finally:
        stop_sweeper()
        await db.close()


app = FastAPI(title="Lumos", version="0.1.0", lifespan=lifespan)


def _error_response(status_code: int, error: str, detail: str | None = None) -> JSONResponse:
    payload: dict[str, str] = {"error": error}
    if detail is not None:
        payload["detail"] = detail
    return JSONResponse(status_code=status_code, content=payload)


def _audit_event_response(event) -> AuditEventResponse:
    return AuditEventResponse(
        id=str(event.id),
        timestamp=event.timestamp,
        event_type=event.event_type,
        agent_id=event.agent_id,
        session_id=event.session_id,
        capability_id=event.capability_id,
        audience=event.audience,
        tool_name=event.tool_name,
        decision=event.decision,
        reason=event.reason,
        event_hash=event.event_hash,
        prev_hash=event.prev_hash,
    )


def _session_response(session) -> SessionResponse:
    return SessionResponse(
        session_id=session.session_id,
        token=None,
        expires_at=session.expires_at,
        agent_id=session.agent_id,
        kid=session.kid,
        issued_at=session.issued_at,
        status=session.status,
        revoked_at=session.revoked_at,
        parent_session_id=session.parent_session_id,
    )


def _agent_with_stats_response(agent: dict) -> AgentWithStatsResponse:
    return AgentWithStatsResponse(
        agent_id=agent["agent_id"],
        display_name=agent["display_name"],
        status=agent["status"],
        created_at=agent["created_at"],
        revoked_at=agent["revoked_at"],
        stats=AgentStats(
            total_calls=int(agent["total_calls"]),
            allowed_calls=int(agent["allowed_calls"]),
            denied_calls=int(agent["denied_calls"]),
            last_seen=agent["last_seen"],
        ),
    )


def _budget_limit_for(agent_id: str) -> int | None:
    budgets = get_policy().get("budgets") or {}
    for candidate in (agent_id, "*"):
        config = budgets.get(candidate)
        if isinstance(config, dict):
            if "limit" in config:
                return int(config["limit"])
    return None


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        if isinstance(exc.detail, dict):
            payload = exc.detail
            if "error" not in payload and "detail" in payload:
                payload = {"error": str(payload["detail"])}
        else:
            payload = {"error": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content=payload)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": "validation error", "detail": str(exc)},
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": exc.errors()},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/db/init", dependencies=[Depends(require_admin)])
async def init_database() -> dict[str, str]:
    await db.init_schema()
    return {"status": "initialized"}


@app.post("/v1/agents", response_model=AgentResponse, dependencies=[Depends(require_admin)])
async def create_agent(request: AgentCreateRequest) -> AgentResponse:
    async with db.acquire() as conn:
        try:
            agent = await repositories.create_agent(
                conn,
                agent_id=request.agent_id,
                display_name=request.display_name,
            )
        except UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail="agent already exists") from exc

    return AgentResponse(
        agent_id=agent.agent_id,
        display_name=agent.display_name,
        status=agent.status,
    )


@app.post(
    "/v1/agents/{agent_id}/keys",
    response_model=AgentKeyResponse,
    dependencies=[Depends(require_admin)],
)
async def create_agent_key(agent_id: str, request: AgentKeyCreateRequest) -> AgentKeyResponse:
    try:
        kid = compute_kid(request.public_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async with db.acquire() as conn:
        agent = await repositories.get_agent(conn, agent_id)
        if agent is None or agent.status != "active":
            raise HTTPException(status_code=404, detail="active agent not found")

        try:
            key = await repositories.create_agent_key(
                conn,
                agent_id=agent_id,
                kid=kid,
                public_key=request.public_key,
            )
        except UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail="agent key already exists") from exc

    return AgentKeyResponse(
        agent_id=key.agent_id,
        kid=key.kid,
        public_key=key.public_key,
        status=key.status,
    )


@app.post("/v1/auth/nonce", response_model=NonceResponse)
async def create_nonce() -> NonceResponse:
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.nonce_ttl_seconds)
    nonce = secrets.token_urlsafe(32)

    async with db.acquire() as conn:
        record = await repositories.create_auth_nonce(conn, nonce, expires_at)

    return NonceResponse(nonce=record.nonce, expires_at=record.expires_at)


@app.post("/v1/auth/session", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest) -> SessionResponse:
    async with db.acquire() as conn:
        if abs(int(time.time()) - request.timestamp) > settings.timestamp_skew_seconds:
            await repositories.create_audit_event(
                conn,
                event_type="session_denied",
                decision="deny",
                reason="timestamp skew exceeded",
                metadata={"agent_id": request.agent_id},
            )
            raise HTTPException(status_code=401, detail="invalid timestamp")

        agent = await repositories.get_agent(conn, request.agent_id)
        if agent is None or agent.status != "active":
            await repositories.create_audit_event(
                conn,
                event_type="session_denied",
                decision="deny",
                reason="agent not active",
                metadata={"agent_id": request.agent_id},
            )
            raise HTTPException(status_code=401, detail="invalid agent")

        key = await repositories.get_agent_key(conn, request.agent_id, request.kid)
        if key is None or key.status != "active":
            await repositories.create_audit_event(
                conn,
                event_type="session_denied",
                decision="deny",
                agent_id=request.agent_id,
                reason="key not active",
                metadata={"kid": request.kid},
            )
            raise HTTPException(status_code=401, detail="invalid key")

        if not verify_auth_signature(
            public_key=key.public_key,
            agent_id=request.agent_id,
            kid=request.kid,
            nonce=request.nonce,
            timestamp=request.timestamp,
            signature=request.signature,
        ):
            await repositories.create_audit_event(
                conn,
                event_type="session_denied",
                decision="deny",
                agent_id=request.agent_id,
                reason="invalid signature",
                metadata={"kid": request.kid},
            )
            raise HTTPException(status_code=401, detail="invalid signature")

        issued_at = now_utc()
        expires_at = default_session_expiry(issued_at)
        session_id = new_session_id()
        
        token = create_session_token(
            private_key=app.state.issuer_private_key,
            agent_id=request.agent_id,
            session_id=session_id,
            kid=request.kid,
            issued_at=issued_at,
            expires_at=expires_at,
        )

        try:
            async with conn.transaction():
                nonce = await repositories.consume_auth_nonce(conn, request.nonce)
                if nonce is None:
                    raise ValueError("invalid nonce")

                session = await repositories.create_session(
                    conn,
                    session_id=session_id,
                    agent_id=request.agent_id,
                    kid=request.kid,
                    issued_at=issued_at,
                    expires_at=expires_at,
                )
                
                await repositories.create_audit_event(
                    conn,
                    event_type="session_issued",
                    decision="issue",
                    agent_id=request.agent_id,
                    session_id=session.session_id,
                    reason="session issued",
                    metadata={"kid": request.kid},
                )
        except ValueError:
            await repositories.create_audit_event(
                conn,
                event_type="session_denied",
                decision="deny",
                reason="nonce missing, consumed, or expired",
                metadata={"agent_id": request.agent_id},
            )
            raise HTTPException(status_code=401, detail="invalid nonce")

    return SessionResponse(
        session_id=session.session_id,
        token=token,
        expires_at=session.expires_at,
    )


@app.post("/v1/capabilities", response_model=CapabilityResponse)
async def create_capability(
    request: CapabilityCreateRequest,
    authorization: str | None = Header(default=None),
) -> CapabilityResponse:
    session_token = session_token_from_header(authorization)
    issued_at = now_utc()

    async with db.acquire() as conn:
        try:
            _, session = await validate_session_token(
                conn,
                app.state.issuer_public_key,
                session_token,
            )
        except TokenValidationError as exc:
            await repositories.create_audit_event(
                conn,
                event_type="capability_denied",
                decision="deny",
                reason=str(exc),
                metadata={"audience": request.audience, "tools": request.tools},
            )
            raise HTTPException(status_code=401, detail="invalid session token") from exc

        expires_at = default_capability_expiry(issued_at, session)
        if expires_at > session.expires_at or expires_at <= issued_at:
            await repositories.create_audit_event(
                conn,
                event_type="capability_denied",
                decision="deny",
                agent_id=session.agent_id,
                session_id=session.session_id,
                reason="session expires before capability can be issued",
                metadata={"audience": request.audience, "tools": request.tools},
            )
            raise HTTPException(status_code=401, detail="invalid session token")

        capability_id = new_capability_id()
        token = create_capability_token(
            private_key=app.state.issuer_private_key,
            agent_id=session.agent_id,
            session_id=session.session_id,
            capability_id=capability_id,
            audience=request.audience,
            tools=request.tools,
            constraints=request.constraints,
            issued_at=issued_at,
            expires_at=expires_at,
        )

        async with conn.transaction():
            capability = await repositories.create_capability(
                conn,
                capability_id=capability_id,
                session_id=session.session_id,
                agent_id=session.agent_id,
                audience=request.audience,
                tools=request.tools,
                constraints=request.constraints,
                issued_at=issued_at,
                expires_at=expires_at,
            )
            await repositories.create_audit_event(
                conn,
                event_type="capability_issued",
                decision="issue",
                agent_id=session.agent_id,
                session_id=session.session_id,
                capability_id=capability.capability_id,
                audience=request.audience,
                reason="capability issued",
                metadata={"tools": request.tools},
            )

    return CapabilityResponse(
        capability_id=capability.capability_id,
        token=token,
        expires_at=capability.expires_at,
    )


@app.post("/v1/sessions/{session_id}/revoke", dependencies=[Depends(require_admin)])
async def revoke_session(session_id: str) -> dict[str, str]:
    async with db.acquire() as conn:
        session = await repositories.revoke_session(conn, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        await repositories.create_audit_event(
            conn,
            event_type="session_revoked",
            decision="revoke",
            agent_id=session.agent_id,
            session_id=session.session_id,
            reason="session revoked",
        )
    return {"status": "revoked", "session_id": session_id}


@app.post("/v1/capabilities/{capability_id}/revoke", dependencies=[Depends(require_admin)])
async def revoke_capability(capability_id: str) -> dict[str, str]:
    async with db.acquire() as conn:
        capability = await repositories.revoke_capability(conn, capability_id)
        if capability is None:
            raise HTTPException(status_code=404, detail="capability not found")
        await repositories.create_audit_event(
            conn,
            event_type="capability_revoked",
            decision="revoke",
            agent_id=capability.agent_id,
            session_id=capability.session_id,
            capability_id=capability.capability_id,
            audience=capability.audience,
            reason="capability revoked",
        )
    return {"status": "revoked", "capability_id": capability_id}


@app.post("/v1/agents/{agent_id}/revoke", dependencies=[Depends(require_admin)])
async def revoke_agent_endpoint(agent_id: str) -> dict[str, str]:
    async with db.acquire() as conn:
        agent = await repositories.revoke_agent(conn, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        await repositories.create_audit_event(
            conn,
            event_type="agent.revoked",
            agent_id=agent_id,
            decision="revoke",
        )
    return {"status": "revoked", "agent_id": agent_id}


@app.post(
    "/v1/agents/{agent_id}/keys/{kid}/revoke",
    dependencies=[Depends(require_admin)],
)
async def revoke_agent_key_endpoint(agent_id: str, kid: str) -> dict[str, str]:
    async with db.acquire() as conn:
        key = await repositories.revoke_agent_key(conn, agent_id, kid)
        if not key:
            raise HTTPException(status_code=404, detail="Key not found")
        await repositories.create_audit_event(
            conn,
            event_type="key.revoked",
            agent_id=agent_id,
            decision="revoke",
        )
    return {"status": "revoked", "agent_id": agent_id, "kid": kid}


@app.post("/v1/validate/session")
async def validate_session(
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    token = session_token_from_header(authorization)
    async with db.acquire() as conn:
        try:
            _, session = await validate_session_token(conn, app.state.issuer_public_key, token)
        except TokenValidationError as exc:
            raise HTTPException(status_code=401, detail="invalid session token") from exc
    return {"status": "valid", "session_id": session.session_id, "agent_id": session.agent_id}


@app.post("/v1/validate/capability")
async def validate_capability(
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    token = session_token_from_header(authorization)
    async with db.acquire() as conn:
        try:
            _, capability = await validate_capability_token(conn, app.state.issuer_public_key, token)
        except TokenValidationError as exc:
            raise HTTPException(status_code=401, detail="invalid capability token") from exc
    return {
        "status": "valid",
        "capability_id": capability.capability_id,
        "session_id": capability.session_id,
        "agent_id": capability.agent_id,
    }


@app.post("/v1/enforce", response_model=EnforceResponse)
async def enforce(request: EnforceRequest) -> EnforceResponse:
    async with db.acquire() as conn:
        try:
            _, capability = await validate_capability_token(
                conn,
                app.state.issuer_public_key,
                request.capability_token,
                audience=request.audience,
            )
        except TokenValidationError:
            return EnforceResponse(allowed=False, reason="invalid capability")

    if request.tool and request.tool not in capability.tools:
        return EnforceResponse(allowed=False, reason="tool not allowed")

    return EnforceResponse(allowed=True)


@app.get("/api/events", response_model=AuditEventListResponse)
async def list_events(
    agent_id: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(require_admin),
) -> AuditEventListResponse:
    async with db.acquire() as conn:
        events, total = await repositories.list_audit_events(
            conn,
            agent_id=agent_id,
            tool_name=tool_name,
            decision=decision,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )
    return AuditEventListResponse(
        events=[_audit_event_response(event) for event in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/api/events/{event_id}", response_model=AuditEventResponse)
async def get_event(
    event_id: str,
    _: None = Depends(require_admin),
) -> AuditEventResponse:
    async with db.acquire() as conn:
        try:
            event = await repositories.get_audit_event(conn, event_id)
        except ValueError:
            event = None
    if event is None:
        raise HTTPException(status_code=404, detail={"error": "event not found"})
    return _audit_event_response(event)


@app.get("/api/agents", response_model=AgentListResponse)
async def list_agents_with_stats_endpoint(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(require_admin),
) -> AgentListResponse:
    async with db.acquire() as conn:
        agents, total = await repositories.list_agents_with_stats(
            conn,
            status=status,
            limit=limit,
            offset=offset,
        )
    return AgentListResponse(
        agents=[_agent_with_stats_response(agent) for agent in agents],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/api/agents/{agent_id}", response_model=AgentWithStatsResponse)
async def get_agent_with_stats_endpoint(
    agent_id: str,
    _: None = Depends(require_admin),
) -> AgentWithStatsResponse:
    async with db.acquire() as conn:
        agent = await repositories.get_agent_with_stats(conn, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail={"error": "agent not found"})
    return _agent_with_stats_response(agent)


@app.get("/api/stats/summary", response_model=SummaryStatsResponse)
async def get_summary_stats_endpoint(
    _: None = Depends(require_admin),
) -> SummaryStatsResponse:
    async with db.acquire() as conn:
        stats = await repositories.get_summary_stats(conn)
        audit_chain_verified, _reason = await repositories.verify_audit_chain(conn, limit=100)
    return SummaryStatsResponse(
        **stats,
        audit_chain_verified=audit_chain_verified,
    )


@app.get("/api/stats/costs", response_model=CostsResponse)
async def get_costs_endpoint(
    _: None = Depends(require_admin),
) -> CostsResponse:
    async with db.acquire() as conn:
        rows = await repositories.get_budget_state(conn)
    return CostsResponse(
        agents=[
            CostEntry(
                agent_id=row["agent_id"],
                period=row["period"],
                usage=int(row["usage"]),
                limit=_budget_limit_for(row["agent_id"]),
            )
            for row in rows
        ]
    )


@app.get("/api/policy", response_model=PolicyResponse)
async def get_policy_endpoint(
    _: None = Depends(require_admin),
) -> PolicyResponse:
    return PolicyResponse(
        policy=get_policy(),
        policy_dir=get_policy_dir(),
        fingerprint=get_policy_fingerprint(),
    )


@app.put("/api/policy")
async def update_policy_endpoint(
    request: PolicyUpdateRequest,
    _: None = Depends(require_admin),
):
    try:
        parsed = yaml.safe_load(request.yaml_content) or {}
        if not isinstance(parsed, dict):
            raise ValueError("policy must be an object")
        _validate_policy(parsed)
    except Exception as exc:
        return _error_response(400, "invalid policy", str(exc))

    policy_path = Path("policies") / "default.yaml"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(request.yaml_content, encoding="utf-8")
    reload_policy(policy_path.parent)
    return {"status": "applied"}


@app.post("/api/policy/validate", response_model=PolicyValidateResponse)
async def validate_policy_endpoint(
    request: PolicyValidateRequest,
    _: None = Depends(require_admin),
) -> PolicyValidateResponse:
    try:
        parsed = yaml.safe_load(request.yaml_content) or {}
        if not isinstance(parsed, dict):
            raise ValueError("policy must be an object")
        _validate_policy(parsed)
    except Exception as exc:
        return PolicyValidateResponse(valid=False, error=str(exc))
    return PolicyValidateResponse(valid=True, error=None)


@app.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions_endpoint(
    agent_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(require_admin),
) -> SessionListResponse:
    async with db.acquire() as conn:
        sessions, total = await repositories.list_sessions(
            conn,
            agent_id=agent_id,
            status=status,
            limit=limit,
            offset=offset,
        )
    return SessionListResponse(
        sessions=[_session_response(session) for session in sessions],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/api/sessions/{session_id}")
async def get_session_endpoint(
    session_id: str,
    _: None = Depends(require_admin),
):
    async with db.acquire() as conn:
        session = await repositories.get_session(conn, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"error": "session not found"})
    return _session_response(session).model_dump()


@app.get("/api/audit/verify", response_model=AuditChainVerifyResponse)
async def verify_audit_chain_endpoint(
    limit: int = Query(default=1000, ge=1, le=10000),
    _: None = Depends(require_admin),
) -> AuditChainVerifyResponse:
    async with db.acquire() as conn:
        valid, reason = await repositories.verify_audit_chain(conn, limit=limit)
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS total
            FROM (
                SELECT id
                FROM audit_events
                WHERE event_hash IS NOT NULL
                ORDER BY timestamp ASC
                LIMIT $1
            ) AS limited_events
            """,
            limit,
        )
    return AuditChainVerifyResponse(
        valid=valid,
        reason=reason,
        events_checked=int(row["total"]),
    )

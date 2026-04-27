from datetime import UTC, datetime
import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from lumos.auth.tokens import TokenValidationError, validate_capability_token
from lumos.db import db
from lumos.policy import budget, engine as policy_engine
from lumos.db.models import Capability
from lumos.proxy.audit import ProxyAuditEvent
from lumos.proxy.identity import resolve_agent_id
from lumos.proxy.router import RouteResolutionError, Router
from lumos.proxy.transport.http_sse import MCPParseError, mcp_error_response, parse_request


logger = logging.getLogger(__name__)


async def handle_proxy_request(request: Request) -> JSONResponse | StreamingResponse:
    try:
        parsed = await parse_request(request)
    except MCPParseError as exc:
        return mcp_error_response(exc.message, request_id=exc.request_id, code=exc.code)

    agent_id: str | None = None
    capability_token = _bearer_token(request)
    router: Router = request.app.state.router
    client: httpx.AsyncClient = request.app.state.http_client
    audit_queue = request.app.state.audit_queue

    upstream_url: str
    allowed = True
    reason = "passthrough"

    if parsed.requires_enforcement:
        agent_id = resolve_agent_id(request)
        if not _has_well_formed_bearer_token(capability_token):
            audit_queue.push(
                ProxyAuditEvent(
                    agent_id=agent_id,
                    tool=parsed.tool_name,
                    allowed=False,
                    reason="invalid capability token",
                    timestamp=datetime.now(UTC),
                )
            )
            return mcp_error_response(
                "access denied: invalid capability token",
                request_id=parsed.request_id,
            )

        try:
            upstream_url = router.resolve_upstream(parsed.tool_name)
        except RouteResolutionError as exc:
            audit_queue.push(
                ProxyAuditEvent(
                    agent_id=agent_id,
                    tool=parsed.tool_name,
                    allowed=False,
                    reason=str(exc),
                    timestamp=datetime.now(UTC),
                )
            )
            return mcp_error_response(str(exc), request_id=parsed.request_id)

        try:
            capability = await _validate_capability_request(
                request=request,
                capability_token=capability_token,
                audience=upstream_url,
                tool_name=parsed.tool_name,
            )
            agent_id = capability.agent_id
        except TokenValidationError as exc:
            audit_queue.push(
                ProxyAuditEvent(
                    agent_id=agent_id,
                    tool=parsed.tool_name,
                    allowed=False,
                    reason="invalid capability token",
                    timestamp=datetime.now(UTC),
                    metadata={"arguments": parsed.arguments},
                )
            )
            return mcp_error_response(
                f"access denied: {exc}",
                request_id=parsed.request_id,
            )

        try:
            decision = await policy_engine.evaluate(
                {
                    "agent_id": agent_id,
                    "tool_name": parsed.tool_name,
                    "arguments": parsed.arguments,
                    "timestamp": datetime.now(UTC),
                }
            )
            allowed = decision.action == "allow"
            reason = decision.reason or decision.rule_name or decision.action
            if not allowed:
                audit_queue.push(
                    ProxyAuditEvent(
                        agent_id=agent_id,
                        tool=parsed.tool_name,
                        allowed=False,
                        reason=reason,
                        timestamp=datetime.now(UTC),
                        metadata={"arguments": parsed.arguments},
                    )
                )
                return mcp_error_response(f"access denied: {reason}", request_id=parsed.request_id)

            reason = "allowed"
        except Exception as exc:
            logger.exception("policy fail-open triggered")
            allowed = True
            reason = f"fail-open: {exc}"
    else:
        agent_id = resolve_agent_id(request)
        try:
            upstream_url = router.default_upstream()
        except RouteResolutionError as exc:
            return mcp_error_response(str(exc), request_id=parsed.request_id)

    audit_queue.push(
        ProxyAuditEvent(
            agent_id=agent_id,
            tool=parsed.tool_name,
            allowed=allowed,
            reason=reason,
            timestamp=datetime.now(UTC),
            metadata={"arguments": parsed.arguments},
        )
    )

    try:
        upstream_response = await _stream_upstream_response(
            client=client,
            upstream_url=upstream_url,
            body=parsed.raw_body,
        )
    except httpx.HTTPError as exc:
        logger.exception("upstream request failed")
        return mcp_error_response(f"upstream request failed: {exc}", request_id=parsed.request_id)

    headers = {}
    content_type = upstream_response.headers.get("content-type")
    if content_type:
        headers["content-type"] = content_type

    return StreamingResponse(
        _stream_response_body(upstream_response),
        status_code=upstream_response.status_code,
        headers=headers,
        background=BackgroundTask(
            _finish_upstream_response,
            upstream_response,
            agent_id,
            parsed.requires_enforcement,
            upstream_response.status_code,
        ),
    )


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        return authorization[len("Bearer ") :]
    return ""


def _has_well_formed_bearer_token(token: str) -> bool:
    if not token:
        return False
    parts = token.split(".")
    return len(parts) == 3 and all(parts)


async def _validate_capability_request(
    request: Request,
    capability_token: str,
    audience: str,
    tool_name: str | None,
) -> Capability:
    async with db.acquire() as conn:
        _, capability = await validate_capability_token(
            conn,
            request.app.state.issuer_public_key,
            capability_token,
            audience=audience,
        )
    if tool_name and tool_name not in capability.tools:
        raise TokenValidationError("tool not allowed")
    return capability


async def _stream_upstream_response(
    client: httpx.AsyncClient,
    upstream_url: str,
    body: bytes,
) -> httpx.Response:
    request = client.build_request(
        "POST",
        upstream_url,
        content=body,
        headers={"content-type": "application/json"},
    )
    return await client.send(request, stream=True)


async def _finish_upstream_response(
    response: httpx.Response,
    agent_id: str,
    should_account_budget: bool,
    status_code: int,
) -> None:
    try:
        await response.aclose()
    finally:
        if should_account_budget and status_code >= 400:
            try:
                await budget.release_budget(agent_id, budget.default_cost(agent_id))
            except Exception:
                logger.exception("failed to release policy budget")


async def _stream_response_body(response: httpx.Response):
    if response.is_stream_consumed:
        yield response.content
        return
    async for chunk in response.aiter_raw():
        yield chunk

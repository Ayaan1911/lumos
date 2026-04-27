from dataclasses import dataclass
import json
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class MCPParseError(Exception):
    def __init__(self, message: str, request_id: Any = None, code: int = -32000) -> None:
        super().__init__(message)
        self.message = message
        self.request_id = request_id
        self.code = code


@dataclass(frozen=True)
class ParsedMCPRequest:
    raw_body: bytes
    payload: dict[str, Any]
    request_id: Any
    method: str
    tool_name: str | None
    arguments: dict[str, Any]
    requires_enforcement: bool


def mcp_error_response(message: str, request_id: Any = None, code: int = -32000) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message,
            },
            "id": request_id,
        },
    )


async def parse_request(request: Request) -> ParsedMCPRequest:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise MCPParseError("invalid JSON", request_id=None) from exc

    if not isinstance(payload, dict):
        raise MCPParseError("invalid JSON-RPC request")

    request_id = payload.get("id")
    if payload.get("jsonrpc") != "2.0":
        raise MCPParseError("invalid jsonrpc version", request_id=request_id)

    method = payload.get("method")
    if not isinstance(method, str) or not method:
        raise MCPParseError("missing method", request_id=request_id)

    if method != "tools/call":
        return ParsedMCPRequest(
            raw_body=raw_body,
            payload=payload,
            request_id=request_id,
            method=method,
            tool_name=None,
            arguments={},
            requires_enforcement=False,
        )

    params = payload.get("params")
    if not isinstance(params, dict):
        raise MCPParseError("missing params for tools/call", request_id=request_id)

    tool_name = params.get("name")
    if not isinstance(tool_name, str) or not tool_name:
        raise MCPParseError("missing tool name", request_id=request_id)

    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        raise MCPParseError("invalid tool arguments", request_id=request_id)

    return ParsedMCPRequest(
        raw_body=raw_body,
        payload=payload,
        request_id=request_id,
        method=method,
        tool_name=tool_name,
        arguments=arguments,
        requires_enforcement=True,
    )


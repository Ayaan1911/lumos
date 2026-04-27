import hashlib

from fastapi import Request


def resolve_agent_id(request: Request) -> str:
    explicit_agent = request.headers.get("x-lumos-agent-id")
    if explicit_agent:
        return explicit_agent

    client_name = request.headers.get("x-mcp-client-name")
    if client_name:
        return client_name

    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :]
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    if request.client and request.client.host:
        return request.client.host

    return "unknown-client"


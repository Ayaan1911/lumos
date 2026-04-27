import asyncio
from datetime import UTC, datetime
import json
from types import SimpleNamespace

import httpx
import pytest

from lumos.policy.loader import reload_policy
from lumos.proxy.audit import AuditQueue, ProxyAuditEvent
from lumos.proxy.main import app as proxy_app
from lumos.proxy import proxy as proxy_module
from lumos.proxy.router import Router


@pytest.fixture(autouse=True)
def bypass_capability_validation(monkeypatch):
    async def _valid_capability(*args, **kwargs):
        return SimpleNamespace(agent_id="agent:test", tools=["tool.echo"])

    monkeypatch.setattr(proxy_module, "_validate_capability_request", _valid_capability)


class ChunkedStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            await asyncio.sleep(0)
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


class RecordingAuditQueue:
    def __init__(self) -> None:
        self.events = []

    def push(self, event: ProxyAuditEvent) -> None:
        self.events.append(event)


async def _proxy_client(tmp_path, handler, routes: dict[str, str] | None = None):
    config_path = tmp_path / "lumos.config.yaml"
    route_lines = routes or {"tool.echo": "http://upstream.test/mcp"}
    config_path.write_text(
        "\n".join(
            ["routes:"]
            + [f"  {json.dumps(pattern)}: {upstream}" for pattern, upstream in route_lines.items()]
        ),
        encoding="utf-8",
    )
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "default.yaml").write_text(
        "\n".join(
            [
                "rules:",
                '  - name: "allow-echo"',
                '    tool: "tool.echo"',
                '    action: "allow"',
            ]
        ),
        encoding="utf-8",
    )
    reload_policy(policy_dir)
    proxy_app.state.router = Router(config_path)
    proxy_app.state.audit_queue = RecordingAuditQueue()
    proxy_app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = httpx.ASGITransport(app=proxy_app)
    client = httpx.AsyncClient(transport=transport, base_url="http://proxy.test")
    return client


@pytest.mark.asyncio
async def test_malformed_json_rpc_returns_error_without_upstream(tmp_path):
    upstream_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal upstream_calls
        upstream_calls += 1
        return httpx.Response(500, json={"detail": "should not be called"})

    client = await _proxy_client(tmp_path, handler)
    try:
        cases = [
            b"{",
            json.dumps([]).encode("utf-8"),
            json.dumps({"jsonrpc": "1.0", "id": "bad", "method": "tools/call"}).encode("utf-8"),
            json.dumps({"jsonrpc": "2.0", "id": "bad"}).encode("utf-8"),
            json.dumps({"jsonrpc": "2.0", "id": "bad", "method": "tools/call"}).encode("utf-8"),
            json.dumps(
                {"jsonrpc": "2.0", "id": "bad", "method": "tools/call", "params": {"name": ""}}
            ).encode("utf-8"),
        ]

        for body in cases:
            response = await client.post("/proxy", content=body, headers={"content-type": "application/json"})
            payload = response.json()
            assert response.status_code == 200
            assert payload["jsonrpc"] == "2.0"
            assert "error" in payload
    finally:
        await client.aclose()
        await proxy_app.state.http_client.aclose()

    assert upstream_calls == 0


@pytest.mark.asyncio
async def test_empty_and_malformed_authorization_fail_closed_before_enforcement(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"allowed": True})

    client = await _proxy_client(tmp_path, handler)
    try:
        request_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "tool.echo", "arguments": {}},
        }
        for headers in ({}, {"Authorization": ""}, {"Authorization": "Bearer malformed"}):
            response = await client.post("/proxy", headers=headers, json=request_body)
            payload = response.json()
            assert "error" in payload
            assert "invalid capability token" in payload["error"]["message"]
    finally:
        await client.aclose()
        await proxy_app.state.http_client.aclose()

    assert calls == []


@pytest.mark.asyncio
async def test_unknown_tool_does_not_fallback_to_default_route(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"allowed": True})

    client = await _proxy_client(tmp_path, handler)
    try:
        response = await client.post(
            "/proxy",
            headers={"Authorization": "Bearer valid.token.value"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "tool.unknown", "arguments": {}},
            },
        )
        payload = response.json()
    finally:
        await client.aclose()
        await proxy_app.state.http_client.aclose()

    assert "error" in payload
    assert "no upstream route" in payload["error"]["message"]
    assert calls == []


@pytest.mark.asyncio
async def test_policy_failure_fails_open_to_resolved_upstream(tmp_path, monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "ok"}]}},
        )

    async def broken_evaluate(ctx):
        raise RuntimeError("policy db down")

    monkeypatch.setattr(proxy_module.policy_engine, "evaluate", broken_evaluate)

    client = await _proxy_client(
        tmp_path,
        handler,
        routes={"tool.echo": "http://upstream.test/specific", "*": "http://upstream.test/default"},
    )
    try:
        response = await client.post(
            "/proxy",
            headers={"Authorization": "Bearer valid.token.value"},
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "tool.echo", "arguments": {}},
            },
        )
    finally:
        await client.aclose()
        await proxy_app.state.http_client.aclose()

    assert response.json()["result"]["content"][0]["text"] == "ok"
    assert calls == ["http://upstream.test/specific"]


@pytest.mark.asyncio
async def test_audit_queue_overflow_drops_without_blocking():
    queue = AuditQueue(maxsize=1)
    first = ProxyAuditEvent("agent:1", "tool.one", True, "first", datetime.now(UTC))
    second = ProxyAuditEvent("agent:1", "tool.two", True, "second", datetime.now(UTC))

    queue.push(first)
    queue.push(second)

    assert queue.queue.qsize() == 1
    assert queue.queue.get_nowait().reason == "second"


@pytest.mark.asyncio
async def test_large_chunked_upstream_response_streams_and_closes(tmp_path):
    stream = ChunkedStream([b"x" * 65536, b"y" * 65536, b"z" * 65536])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream, headers={"content-type": "application/octet-stream"})

    client = await _proxy_client(tmp_path, handler)
    try:
        response = await client.post(
            "/proxy",
            headers={"Authorization": "Bearer valid.token.value"},
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "tool.echo", "arguments": {}},
            },
        )
    finally:
        await client.aclose()
        await proxy_app.state.http_client.aclose()

    assert response.content == (b"x" * 65536) + (b"y" * 65536) + (b"z" * 65536)
    assert stream.closed is True


@pytest.mark.asyncio
async def test_concurrent_proxy_requests_complete_under_mock_load(tmp_path):
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.001)
        payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": {"ok": True}})

    client = await _proxy_client(tmp_path, handler)
    try:
        async def one_request(index: int) -> httpx.Response:
            return await client.post(
                "/proxy",
                headers={"Authorization": "Bearer valid.token.value"},
                json={
                    "jsonrpc": "2.0",
                    "id": index,
                    "method": "tools/call",
                    "params": {"name": "tool.echo", "arguments": {"index": index}},
                },
            )

        responses = await asyncio.gather(*(one_request(index) for index in range(1000)))
    finally:
        await client.aclose()
        await proxy_app.state.http_client.aclose()

    assert all(response.status_code == 200 for response in responses)
    assert all(response.json()["result"]["ok"] is True for response in responses)

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, Request

from lumos.auth.issuer import load_or_create_issuer_private_key, public_key_for
from lumos.db import db
from lumos.db.sweeper import start_sweeper, stop_sweeper
from lumos.policy.loader import start_policy_watcher, stop_policy_watcher
from lumos.proxy.audit import AuditQueue
from lumos.proxy.proxy import handle_proxy_request
from lumos.proxy.router import Router


logger = logging.getLogger(__name__)
CONFIG_PATH = Path("lumos.config.yaml")


def _load_proxy_config() -> dict:
    import yaml

    if not CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.connect()
    config = _load_proxy_config()
    proxy_config = config.get("proxy") or {}

    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    app.state.router = Router(CONFIG_PATH)
    app.state.issuer_public_key = public_key_for(load_or_create_issuer_private_key())
    app.state.audit_queue = AuditQueue(maxsize=int(proxy_config.get("audit_queue_size", 1000)))
    start_policy_watcher(proxy_config.get("policy_dir", "policies"))
    start_sweeper()
    app.state.audit_queue.start()
    try:
        yield
    finally:
        stop_sweeper()
        await stop_policy_watcher()
        await app.state.audit_queue.stop()
        await app.state.http_client.aclose()
        await db.close()


app = FastAPI(title="Lumos Proxy", lifespan=lifespan)
app_proxy = app


@app.post("/proxy")
async def proxy_endpoint(request: Request):
    return await handle_proxy_request(request)

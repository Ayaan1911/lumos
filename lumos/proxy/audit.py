import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from lumos.db import db, repositories
from lumos.policy.pii import redact


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProxyAuditEvent:
    agent_id: str
    tool: str | None
    allowed: bool
    reason: str
    timestamp: datetime
    metadata: dict[str, Any] | None = None


class AuditQueue:
    def __init__(self, maxsize: int = 1000) -> None:
        self.queue: asyncio.Queue[ProxyAuditEvent] = asyncio.Queue(maxsize=maxsize)
        self._consumer_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._consumer_task is None or self._consumer_task.done():
            self._consumer_task = asyncio.create_task(self._consume())

    async def stop(self) -> None:
        if self._consumer_task is None:
            return
        if not self._consumer_task.done():
            try:
                await asyncio.wait_for(self.queue.join(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(
                    "Audit queue did not drain within 5s on shutdown. %d events may be lost.",
                    self.queue.qsize(),
                )
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        self._consumer_task = None

    def push(self, event: ProxyAuditEvent) -> None:
        if self.queue.full():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
                logger.warning("audit queue full; dropped oldest event")
            except asyncio.QueueEmpty:
                pass
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("audit queue full; dropped new event")

    async def join(self) -> None:
        await self.queue.join()

    async def _consume(self) -> None:
        while True:
            event = await self.queue.get()
            try:
                async with db.acquire() as conn:
                    agent = await repositories.get_agent(conn, event.agent_id)
                    metadata = {
                        "timestamp": event.timestamp.isoformat(),
                        "observed_agent_id": event.agent_id,
                    }
                    if event.metadata:
                        metadata.update(await redact(event.metadata))
                    await repositories.create_audit_event(
                        conn,
                        event_type="proxy_request",
                        decision="allow" if event.allowed else "deny",
                        agent_id=event.agent_id if agent is not None else None,
                        tool_name=event.tool,
                        reason=event.reason,
                        metadata=metadata,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("failed to persist proxy audit event")
            finally:
                self.queue.task_done()

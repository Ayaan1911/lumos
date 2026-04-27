import asyncio
import logging

from lumos.db import db


logger = logging.getLogger(__name__)

_sweeper_task: asyncio.Task | None = None


async def _sweep() -> None:
    async with db.acquire() as conn:
        deleted = await conn.execute(
            "DELETE FROM auth_nonces WHERE expires_at < NOW()"
        )
        sessions_expired = await conn.execute(
            """UPDATE sessions SET status = 'expired'
               WHERE status = 'active' AND expires_at < NOW()"""
        )
        caps_expired = await conn.execute(
            """UPDATE capabilities SET status = 'expired'
               WHERE status = 'active' AND expires_at < NOW()"""
        )
        logger.debug(
            "Sweep: %s nonces deleted, %s sessions expired, %s capabilities expired",
            deleted,
            sessions_expired,
            caps_expired,
        )


async def _sweep_loop(interval_seconds: float) -> None:
    while True:
        try:
            await _sweep()
        except Exception:
            logger.exception("Sweeper error (will retry)")
        await asyncio.sleep(interval_seconds)


def start_sweeper(interval_seconds: float = 60.0) -> None:
    global _sweeper_task
    if _sweeper_task is None or _sweeper_task.done():
        _sweeper_task = asyncio.create_task(_sweep_loop(interval_seconds))
        logger.info("Expiry sweeper started (interval=%ss)", interval_seconds)


def stop_sweeper() -> None:
    global _sweeper_task
    if _sweeper_task and not _sweeper_task.done():
        _sweeper_task.cancel()
        _sweeper_task = None
        logger.info("Expiry sweeper stopped")


async def sweep_once() -> None:
    await _sweep()

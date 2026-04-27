from datetime import UTC, datetime, timedelta
from typing import Any

from lumos.db import db
from lumos.policy.loader import get_policy


async def check_rate_limit(agent_id: str, tool: str) -> bool:
    config = _limit_for(agent_id, tool)
    if config is None:
        return True

    window_seconds = int(config["window_seconds"])
    max_calls = int(config["max_calls"])
    now = datetime.now(UTC)
    window_start = now - timedelta(seconds=window_seconds)

    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1), hashtext($2))",
                agent_id,
                tool,
            )
            row = await conn.fetchrow(
                """
                SELECT window_start, call_count
                FROM rate_limit_state
                WHERE agent_id = $1 AND tool = $2
                FOR UPDATE
                """,
                agent_id,
                tool,
            )
            if row is None or row["window_start"] <= window_start:
                await conn.execute(
                    """
                    INSERT INTO rate_limit_state (agent_id, tool, window_start, call_count)
                    VALUES ($1, $2, $3, 1)
                    ON CONFLICT (agent_id, tool)
                    DO UPDATE SET window_start = EXCLUDED.window_start, call_count = 1
                    """,
                    agent_id,
                    tool,
                    now,
                )
                return True

            if row["call_count"] >= max_calls:
                return False

            await conn.execute(
                """
                UPDATE rate_limit_state
                SET call_count = call_count + 1
                WHERE agent_id = $1 AND tool = $2
                """,
                agent_id,
                tool,
            )
            return True


def _limit_for(agent_id: str, tool: str) -> dict[str, Any] | None:
    return _config_for(get_policy().get("rate_limits") or {}, agent_id, tool)


def _config_for(configs: dict[str, Any], agent_id: str, tool: str) -> dict[str, Any] | None:
    for candidate_agent in (agent_id, "*"):
        block = configs.get(candidate_agent)
        if not isinstance(block, dict):
            continue
        if _is_direct_config(block):
            return block
        for candidate_tool in (tool, "*"):
            config = block.get(candidate_tool)
            if isinstance(config, dict):
                return config
    return None


def _is_direct_config(block: dict[str, Any]) -> bool:
    return "window_seconds" in block or "max_calls" in block

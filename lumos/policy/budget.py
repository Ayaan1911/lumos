from datetime import UTC, datetime
from typing import Any

from lumos.db import db
from lumos.policy.loader import get_policy


async def check_budget(agent_id: str) -> bool:
    config = _budget_for(agent_id)
    if config is None:
        return True

    period = _current_period(config["period"])
    limit = int(config["limit"])
    cost = default_cost(agent_id)
    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1), hashtext($2))", agent_id, period)
            row = await conn.fetchrow(
                """
                SELECT usage
                FROM budget_state
                WHERE agent_id = $1 AND period = $2
                FOR UPDATE
                """,
                agent_id,
                period,
            )
            usage = row["usage"] if row else 0
            if usage + cost > limit:
                return False
            new_usage = usage + cost
            await conn.execute(
                """
                INSERT INTO budget_state (agent_id, period, usage)
                VALUES ($1, $2, $3)
                ON CONFLICT (agent_id, period)
                DO UPDATE SET usage = EXCLUDED.usage
                """,
                agent_id,
                period,
                new_usage,
            )
            return True


async def update_budget(agent_id: str, cost: int) -> None:
    config = _budget_for(agent_id)
    if config is None:
        return
    if isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0:
        return

    period = _current_period(config["period"])
    limit = int(config["limit"])
    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1), hashtext($2))", agent_id, period)
            row = await conn.fetchrow(
                """
                SELECT usage
                FROM budget_state
                WHERE agent_id = $1 AND period = $2
                FOR UPDATE
                """,
                agent_id,
                period,
            )
            usage = row["usage"] if row else 0
            new_usage = min(usage + cost, limit)
            await conn.execute(
                """
                INSERT INTO budget_state (agent_id, period, usage)
                VALUES ($1, $2, $3)
                ON CONFLICT (agent_id, period)
                DO UPDATE SET usage = EXCLUDED.usage
                """,
                agent_id,
                period,
                new_usage,
            )


async def release_budget(agent_id: str, cost: int) -> None:
    config = _budget_for(agent_id)
    if config is None:
        return
    if isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0:
        return

    period = _current_period(config["period"])
    async with db.acquire() as conn:
        await conn.execute(
            """
            UPDATE budget_state
            SET usage = GREATEST(0, usage - $1)
            WHERE agent_id = $2 AND period = $3
            """,
            cost,
            agent_id,
            period,
        )


def default_cost(agent_id: str) -> int:
    config = _budget_for(agent_id)
    if config is None:
        return 1
    return int(config.get("default_cost", 1))


def _budget_for(agent_id: str) -> dict[str, Any] | None:
    budgets = get_policy().get("budgets") or {}
    for candidate in (agent_id, "*"):
        config = budgets.get(candidate)
        if isinstance(config, dict):
            return config
    return None


def _current_period(period: str) -> str:
    now = datetime.now(UTC)
    if period == "monthly":
        return now.strftime("%Y-%m")
    return now.strftime("%Y-%m-%d")

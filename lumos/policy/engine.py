from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any, Literal

from lumos.policy.budget import check_budget
from lumos.policy.loader import get_policy
from lumos.policy.matchers import MATCHERS
from lumos.policy.rate_limiter import check_rate_limit


@dataclass(frozen=True)
class Decision:
    action: Literal["allow", "deny"]
    rule_name: str | None = None
    reason: str | None = None


async def evaluate(ctx: dict[str, Any]) -> Decision:
    agent_id = str(ctx["agent_id"])
    tool_name = str(ctx["tool_name"])
    policy = get_policy()

    if not await check_rate_limit(agent_id, tool_name):
        return Decision("deny", reason="rate limit exceeded")
    if not await check_budget(agent_id):
        return Decision("deny", reason="budget exceeded")

    agent_block = _agent_block(policy, agent_id)
    for rule in agent_block.get("rules", []):
        if not _tool_matches(rule["tool"], tool_name):
            continue
        if _conditions_match(ctx, rule.get("when") or {}):
            return Decision(rule["action"], rule_name=rule["name"], reason=rule.get("reason"))

    return Decision("allow")


def _agent_block(policy: dict[str, Any], agent_id: str) -> dict[str, Any]:
    agents = policy.get("agents") or {}
    if agent_id in agents:
        return agents[agent_id]
    for pattern, block in agents.items():
        if pattern != "*" and fnmatchcase(agent_id, pattern):
            return block
    return agents.get("*", {"rules": []})


def _tool_matches(pattern: str, tool_name: str) -> bool:
    return fnmatchcase(tool_name, pattern)


def _conditions_match(ctx: dict[str, Any], conditions: dict[str, Any]) -> bool:
    for field, matcher_config in conditions.items():
        value = _field_value(ctx, field)
        matcher_name, config = next(iter(matcher_config.items()))
        matcher = MATCHERS[matcher_name]
        if not matcher(value, config):
            return False
    return True


def _field_value(ctx: dict[str, Any], field: str) -> Any:
    value: Any = ctx
    for part in field.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value

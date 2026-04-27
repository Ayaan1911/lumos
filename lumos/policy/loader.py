import asyncio
import logging
from pathlib import Path
from typing import Any

import yaml

from lumos.policy.matchers import MATCHERS


logger = logging.getLogger(__name__)
POLICY_DIR = Path("policies")
DEFAULT_POLICY_PATH = POLICY_DIR / "default.yaml"

_policy: dict[str, Any] = {"agents": {"*": {"rules": []}}}
_policy_dir = POLICY_DIR
_watch_task: asyncio.Task[None] | None = None
_fingerprint: dict[Path, int] = {}


def get_policy() -> dict[str, Any]:
    return _policy


def get_policy_dir() -> str:
    return str(_policy_dir) if _policy_dir else "policies"


def get_policy_fingerprint() -> dict:
    return {str(k): v for k, v in _fingerprint.items()}


def load_policy(filepath: str) -> dict[str, Any]:
    data = yaml.safe_load(Path(filepath).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("policy must be an object")
    return _validate_policy(data)


def reload_policy(policy_dir: str | Path = POLICY_DIR) -> bool:
    global _policy, _policy_dir, _fingerprint
    _policy_dir = Path(policy_dir)
    try:
        policy = _load_policy_dir(_policy_dir)
        _policy = policy
        _fingerprint = _current_fingerprint(_policy_dir)
        return True
    except Exception:
        logger.exception("failed to load policy; keeping last valid policy")
        return False


def start_policy_watcher(policy_dir: str | Path = POLICY_DIR, interval_seconds: float = 1.0) -> None:
    global _watch_task
    reload_policy(policy_dir)
    if _watch_task is None or _watch_task.done():
        _watch_task = asyncio.create_task(_watch_loop(interval_seconds))


async def stop_policy_watcher() -> None:
    global _watch_task
    if _watch_task is None:
        return
    _watch_task.cancel()
    try:
        await _watch_task
    except asyncio.CancelledError:
        pass
    _watch_task = None


async def _watch_loop(interval_seconds: float) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        fingerprint = _current_fingerprint(_policy_dir)
        if fingerprint != _fingerprint:
            reload_policy(_policy_dir)


def _load_policy_dir(policy_dir: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {"agents": {}, "rate_limits": {}, "budgets": {}}
    files: list[Path] = []
    default_path = policy_dir / "default.yaml"
    if default_path.exists():
        files.append(default_path)
    files.extend(
        path
        for path in sorted(policy_dir.glob("*.y*ml"))
        if path.name != "default.yaml" and path.is_file()
    )

    for path in files:
        policy = load_policy(str(path))
        _merge_policy(merged, policy)

    if not merged["agents"]:
        merged["agents"]["*"] = {"rules": []}
    return _validate_policy(merged)


def _merge_policy(target: dict[str, Any], policy: dict[str, Any]) -> None:
    for agent_id, block in policy.get("agents", {}).items():
        existing = target["agents"].setdefault(agent_id, {"rules": []})
        existing["rules"].extend(block.get("rules", []))
    target["rate_limits"].update(policy.get("rate_limits", {}))
    target["budgets"].update(policy.get("budgets", {}))


def _validate_policy(data: dict[str, Any]) -> dict[str, Any]:
    allowed_top = {"agents", "rules", "rate_limits", "budgets"}
    unknown = set(data) - allowed_top
    if unknown:
        raise ValueError(f"unknown policy keys: {sorted(unknown)}")

    normalized: dict[str, Any] = {
        "agents": {},
        "rate_limits": data.get("rate_limits") or {},
        "budgets": data.get("budgets") or {},
    }

    agents = data.get("agents") or {}
    if data.get("rules") is not None:
        agents = dict(agents)
        agents.setdefault("*", {})["rules"] = data["rules"]

    if not isinstance(agents, dict):
        raise ValueError("agents must be an object")
    for agent_id, block in agents.items():
        if not isinstance(agent_id, str) or not isinstance(block, dict):
            raise ValueError("agent policy blocks must be objects")
        unknown_block = set(block) - {"rules"}
        if unknown_block:
            raise ValueError(f"unknown agent policy keys: {sorted(unknown_block)}")
        rules = block.get("rules") or []
        if not isinstance(rules, list):
            raise ValueError("rules must be a list")
        normalized["agents"][agent_id] = {"rules": [_validate_rule(rule) for rule in rules]}

    _validate_limit_map(normalized["rate_limits"], "rate_limits", {"window_seconds", "max_calls"})
    _validate_limit_map(normalized["budgets"], "budgets", {"period", "limit", "default_cost"})
    return normalized


def _validate_rule(rule: Any) -> dict[str, Any]:
    if not isinstance(rule, dict):
        raise ValueError("rule must be an object")
    unknown = set(rule) - {"name", "tool", "action", "reason", "when"}
    if unknown:
        raise ValueError(f"unknown rule keys: {sorted(unknown)}")
    if not isinstance(rule.get("name"), str) or not rule["name"]:
        raise ValueError("rule name is required")
    if not isinstance(rule.get("tool"), str) or not rule["tool"]:
        raise ValueError("rule tool is required")
    if rule.get("action") not in {"allow", "deny"}:
        raise ValueError("rule action must be allow or deny")
    if rule.get("reason") is not None and not isinstance(rule["reason"], str):
        raise ValueError("rule reason must be a string")

    when = rule.get("when") or {}
    if not isinstance(when, dict):
        raise ValueError("rule when must be an object")
    for field, matcher_config in when.items():
        if not isinstance(field, str) or not isinstance(matcher_config, dict):
            raise ValueError("matcher config must be an object")
        if len(matcher_config) != 1:
            raise ValueError("matcher config must contain exactly one matcher")
        matcher_name = next(iter(matcher_config))
        if matcher_name not in MATCHERS:
            raise ValueError(f"unknown matcher: {matcher_name}")

    return {
        "name": rule["name"],
        "tool": rule["tool"],
        "action": rule["action"],
        "reason": rule.get("reason"),
        "when": when,
    }


def _validate_limit_map(data: Any, name: str, allowed_keys: set[str]) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be an object")
    for agent_id, tool_map in data.items():
        if not isinstance(agent_id, str) or not isinstance(tool_map, dict):
            raise ValueError(f"{name} entries must be objects")
        if set(tool_map).issubset(allowed_keys):
            _validate_limit_config(tool_map, name, allowed_keys)
            continue
        for tool, config in tool_map.items():
            if not isinstance(tool, str) or not isinstance(config, dict):
                raise ValueError(f"{name} tool entries must be objects")
            _validate_limit_config(config, name, allowed_keys)


def _validate_limit_config(config: dict[str, Any], name: str, allowed_keys: set[str]) -> None:
    unknown = set(config) - allowed_keys
    if unknown:
        raise ValueError(f"unknown {name} keys: {sorted(unknown)}")
    required = {"window_seconds", "max_calls"} if name == "rate_limits" else {"period", "limit"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"missing {name} keys: {sorted(missing)}")
    for key, value in config.items():
        if key == "period":
            if value not in {"daily", "monthly"}:
                raise ValueError("budget period must be daily or monthly")
        elif isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} {key} must be a positive integer")


def _current_fingerprint(policy_dir: Path) -> dict[Path, int]:
    if not policy_dir.exists():
        return {}
    return {
        path: path.stat().st_mtime_ns
        for path in sorted(policy_dir.glob("*.y*ml"))
        if path.is_file()
    }

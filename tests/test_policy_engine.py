import asyncio
from datetime import UTC, datetime

import pytest

from lumos.config import settings
from lumos.db import db
from lumos.policy import budget
from lumos.policy import engine
from lumos.policy.loader import get_policy, reload_policy, start_policy_watcher, stop_policy_watcher
from lumos.policy.matchers import MATCHERS
from lumos.policy.pii import redact


def _write_policy(tmp_path, text: str):
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir(exist_ok=True)
    (policy_dir / "default.yaml").write_text(text, encoding="utf-8")
    return policy_dir


def _ctx(tool_name: str = "tool.echo", arguments: dict | None = None) -> dict:
    return {
        "agent_id": "agent:test",
        "tool_name": tool_name,
        "arguments": arguments or {},
        "timestamp": datetime.now(UTC),
    }


def test_matchers_are_safe_and_correct():
    assert MATCHERS["equals"]("a", "a") is True
    assert MATCHERS["not_equals"]("a", "b") is True
    assert MATCHERS["contains"]("hello", "ell") is True
    assert MATCHERS["not_contains"]("hello", "zzz") is True
    assert MATCHERS["starts_with"]("hello", "he") is True
    assert MATCHERS["regex"]("abc123", r"\d+") is True
    assert MATCHERS["gt"](3, 2) is True
    assert MATCHERS["lt"](2, 3) is True
    assert MATCHERS["in"]("a", ["a", "b"]) is True
    assert MATCHERS["not_in"]("c", ["a", "b"]) is True
    assert MATCHERS["regex"]("abc", "[") is False
    assert MATCHERS["regex"]("a" * 4097, "a+") is False
    assert MATCHERS["regex"]("abc", "a" * 513) is False
    assert MATCHERS["gt"]("3", 2) is False
    assert MATCHERS["contains"](3, "3") is False


@pytest.mark.asyncio
async def test_rule_match_allow(tmp_path):
    policy_dir = _write_policy(
        tmp_path,
        """
agents:
  "*":
    rules:
      - name: "allow-echo"
        tool: "tool.echo"
        action: "allow"
        when:
          arguments.message:
            equals: "hello"
""",
    )
    assert reload_policy(policy_dir) is True

    decision = await engine.evaluate(_ctx(arguments={"message": "hello"}))

    assert decision.action == "allow"
    assert decision.rule_name == "allow-echo"


@pytest.mark.asyncio
async def test_rule_match_deny(tmp_path):
    policy_dir = _write_policy(
        tmp_path,
        """
rules:
  - name: "block-delete"
    tool: "tool.delete"
    action: "deny"
    reason: "dangerous"
""",
    )
    assert reload_policy(policy_dir) is True

    decision = await engine.evaluate(_ctx(tool_name="tool.delete"))

    assert decision.action == "deny"
    assert decision.rule_name == "block-delete"
    assert decision.reason == "dangerous"


@pytest.mark.asyncio
async def test_rate_limit_triggers_deny(conn, test_database_url, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()
    policy_dir = _write_policy(
        tmp_path,
        """
rate_limits:
  "*":
    "*":
      window_seconds: 60
      max_calls: 1
rules:
  - name: "allow-all"
    tool: "*"
    action: "allow"
""",
    )
    assert reload_policy(policy_dir) is True
    try:
        assert (await engine.evaluate(_ctx())).action == "allow"
        decision = await engine.evaluate(_ctx())
    finally:
        await db.close()

    assert decision.action == "deny"
    assert decision.reason == "rate limit exceeded"


@pytest.mark.asyncio
async def test_rate_limit_concurrent_missing_row_allows_only_limit(conn, test_database_url, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()
    policy_dir = _write_policy(
        tmp_path,
        """
rate_limits:
  "*":
    "*":
      window_seconds: 60
      max_calls: 5
rules:
  - name: "allow-all"
    tool: "*"
    action: "allow"
""",
    )
    assert reload_policy(policy_dir) is True
    try:
        decisions = await asyncio.gather(*(engine.evaluate(_ctx()) for _ in range(20)))
    finally:
        await db.close()

    assert sum(decision.action == "allow" for decision in decisions) == 5
    assert sum(decision.reason == "rate limit exceeded" for decision in decisions) == 15


@pytest.mark.asyncio
async def test_budget_triggers_deny(conn, test_database_url, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()
    policy_dir = _write_policy(
        tmp_path,
        """
budgets:
  "*":
    period: "daily"
    limit: 1
    default_cost: 1
rules:
  - name: "allow-all"
    tool: "*"
    action: "allow"
""",
    )
    assert reload_policy(policy_dir) is True
    await conn.execute(
        "INSERT INTO budget_state (agent_id, period, usage) VALUES ($1, $2, $3)",
        "agent:test",
        datetime.now(UTC).strftime("%Y-%m-%d"),
        1,
    )
    try:
        decision = await engine.evaluate(_ctx())
    finally:
        await db.close()

    assert decision.action == "deny"
    assert decision.reason == "budget exceeded"


@pytest.mark.asyncio
async def test_budget_concurrent_reservations_allow_exactly_limit(conn, test_database_url, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_database_url)
    await db.connect()
    policy_dir = _write_policy(
        tmp_path,
        """
budgets:
  "*":
    period: "daily"
    limit: 5
    default_cost: 1
rules:
  - name: "allow-all"
    tool: "*"
    action: "allow"
""",
    )
    assert reload_policy(policy_dir) is True
    try:
        results = await asyncio.gather(*(budget.check_budget("agent:test") for _ in range(10)))
        row = await conn.fetchrow(
            "SELECT usage FROM budget_state WHERE agent_id = $1 AND period = $2",
            "agent:test",
            datetime.now(UTC).strftime("%Y-%m-%d"),
        )
    finally:
        await db.close()

    assert row["usage"] == 5
    assert sum(results) == 5
    assert sum(not result for result in results) == 5


@pytest.mark.asyncio
async def test_hot_reload_updates_rules(tmp_path):
    policy_dir = _write_policy(
        tmp_path,
        """
rules:
  - name: "allow-delete"
    tool: "tool.delete"
    action: "allow"
""",
    )
    start_policy_watcher(policy_dir, interval_seconds=0.1)
    try:
        assert get_policy()["agents"]["*"]["rules"][0]["action"] == "allow"
        await asyncio.sleep(0.2)
        (policy_dir / "default.yaml").write_text(
            """
rules:
  - name: "block-delete"
    tool: "tool.delete"
    action: "deny"
""",
            encoding="utf-8",
        )

        for _ in range(30):
            if get_policy()["agents"]["*"]["rules"][0]["action"] == "deny":
                break
            await asyncio.sleep(0.1)
    finally:
        await stop_policy_watcher()

    assert get_policy()["agents"]["*"]["rules"][0]["name"] == "block-delete"


@pytest.mark.asyncio
async def test_invalid_policy_keeps_last_valid_policy(tmp_path):
    policy_dir = _write_policy(
        tmp_path,
        """
rules:
  - name: "allow-echo"
    tool: "tool.echo"
    action: "allow"
""",
    )
    assert reload_policy(policy_dir) is True
    assert get_policy()["agents"]["*"]["rules"][0]["name"] == "allow-echo"

    (policy_dir / "default.yaml").write_text("rules: [", encoding="utf-8")

    assert reload_policy(policy_dir) is False
    assert get_policy()["agents"]["*"]["rules"][0]["name"] == "allow-echo"


@pytest.mark.asyncio
async def test_incomplete_limit_config_is_rejected_without_replacing_policy(tmp_path):
    policy_dir = _write_policy(
        tmp_path,
        """
rules:
  - name: "allow-echo"
    tool: "tool.echo"
    action: "allow"
""",
    )
    assert reload_policy(policy_dir) is True

    (policy_dir / "default.yaml").write_text(
        """
rate_limits:
  "*":
    "*":
      max_calls: 1
""",
        encoding="utf-8",
    )

    assert reload_policy(policy_dir) is False
    assert get_policy()["agents"]["*"]["rules"][0]["name"] == "allow-echo"


@pytest.mark.asyncio
async def test_pii_redaction_is_recursive():
    value = {
        "email": "person@example.com",
        "nested": ["card 4111 1111 1111 1111", "ip 192.168.1.10"],
        "token": "api_abcdefghijklmnopqrstuvwxyz",
    }

    redacted = await redact(value)

    assert redacted == {
        "email": "[REDACTED]",
        "nested": ["card [REDACTED]", "ip [REDACTED]"],
        "token": "[REDACTED]",
    }

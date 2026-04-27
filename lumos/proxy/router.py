from dataclasses import dataclass
from pathlib import Path

import yaml


class RouteResolutionError(Exception):
    pass


@dataclass(frozen=True)
class RouteRule:
    pattern: str
    upstream: str


class Router:
    def __init__(self, config_path: str | Path = "lumos.config.yaml") -> None:
        self.config_path = Path(config_path)
        self._rules = self._load_rules()

    def _load_rules(self) -> list[RouteRule]:
        if not self.config_path.exists():
            raise RouteResolutionError(f"routing config not found: {self.config_path}")

        config = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        routes = config.get("routes") or {}
        if not isinstance(routes, dict) or not routes:
            raise RouteResolutionError("routing config must define at least one route")

        rules: list[RouteRule] = []
        for pattern, upstream in routes.items():
            if not isinstance(pattern, str) or not isinstance(upstream, str):
                raise RouteResolutionError("route patterns and upstream URLs must be strings")
            rules.append(RouteRule(pattern=pattern, upstream=upstream))
        return rules

    def resolve_upstream(self, tool_name: str) -> str:
        for rule in self._rules:
            if self._matches(rule.pattern, tool_name):
                return rule.upstream
        raise RouteResolutionError(f"no upstream route for tool: {tool_name}")

    def default_upstream(self) -> str:
        return self._rules[0].upstream

    @staticmethod
    def _matches(pattern: str, tool_name: str) -> bool:
        if pattern.endswith("*"):
            return tool_name.startswith(pattern[:-1])
        return pattern == tool_name


def resolve_upstream(tool_name: str, config_path: str | Path = "lumos.config.yaml") -> str:
    return Router(config_path=config_path).resolve_upstream(tool_name)


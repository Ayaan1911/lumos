import re
from typing import Any


MAX_REGEX_VALUE_LENGTH = 4096
MAX_REGEX_PATTERN_LENGTH = 512


def equals(value: Any, config: Any) -> bool:
    return value == config


def not_equals(value: Any, config: Any) -> bool:
    return value != config


def contains(value: Any, config: Any) -> bool:
    if isinstance(value, str) and isinstance(config, str):
        return config in value
    if isinstance(value, (list, tuple, set)):
        return config in value
    return False


def not_contains(value: Any, config: Any) -> bool:
    if isinstance(value, str) and isinstance(config, str):
        return config not in value
    if isinstance(value, (list, tuple, set)):
        return config not in value
    return False


def starts_with(value: Any, config: Any) -> bool:
    if not isinstance(value, str) or not isinstance(config, str):
        return False
    return value.startswith(config)


def regex(value: Any, config: Any) -> bool:
    if not isinstance(value, str) or not isinstance(config, str):
        return False
    if len(value) > MAX_REGEX_VALUE_LENGTH or len(config) > MAX_REGEX_PATTERN_LENGTH:
        return False
    try:
        return bool(re.search(config, value))
    except re.error:
        return False


def gt(value: Any, config: Any) -> bool:
    if isinstance(value, bool) or isinstance(config, bool):
        return False
    if not isinstance(value, (int, float)) or not isinstance(config, (int, float)):
        return False
    return value > config


def lt(value: Any, config: Any) -> bool:
    if isinstance(value, bool) or isinstance(config, bool):
        return False
    if not isinstance(value, (int, float)) or not isinstance(config, (int, float)):
        return False
    return value < config


def in_(value: Any, config: Any) -> bool:
    if not isinstance(config, (list, tuple, set)):
        return False
    return value in config


def not_in(value: Any, config: Any) -> bool:
    if not isinstance(config, (list, tuple, set)):
        return False
    return value not in config


MATCHERS = {
    "equals": equals,
    "not_equals": not_equals,
    "contains": contains,
    "not_contains": not_contains,
    "starts_with": starts_with,
    "regex": regex,
    "gt": gt,
    "lt": lt,
    "in": in_,
    "not_in": not_in,
}

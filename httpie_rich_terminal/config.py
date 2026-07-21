"""Environment-variable driven configuration.

ConverterPlugin has no access to HTTPie's CLI arguments (--format-options is
only passed to formatters), so environment variables are the only knob.
"""

import os
import sys
from dataclasses import dataclass
from typing import Mapping, Optional

ENV_PREFIX = "HTTPIE_RICH_"

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_VALID_PROTOCOLS = frozenset({"kitty", "iterm2"})


@dataclass(frozen=True)
class Config:
    disable: bool
    max_width: Optional[int]
    max_height: Optional[int]
    protocol: Optional[str]
    debug: bool


def _read_bool(env: Mapping[str, str], name: str) -> bool:
    return env.get(ENV_PREFIX + name, "").strip().lower() in _TRUTHY


def _read_positive_int(env: Mapping[str, str], name: str) -> Optional[int]:
    """Parse a positive int, falling back to None on any malformed input."""
    raw = env.get(ENV_PREFIX + name)
    if raw is None:
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        return None
    return value if value > 0 else None


def _read_protocol(env: Mapping[str, str]) -> Optional[str]:
    """Return a forced protocol name, or None for auto-detection."""
    raw = env.get(ENV_PREFIX + "PROTOCOL", "").strip().lower()
    return raw if raw in _VALID_PROTOCOLS else None


def load_config(env: Optional[Mapping[str, str]] = None) -> Config:
    if env is None:
        env = os.environ
    return Config(
        disable=_read_bool(env, "DISABLE"),
        max_width=_read_positive_int(env, "MAX_WIDTH"),
        max_height=_read_positive_int(env, "MAX_HEIGHT"),
        protocol=_read_protocol(env),
        debug=_read_bool(env, "DEBUG"),
    )


def debug_log(config: Config, message: str) -> None:
    """Write a diagnostic line to stderr when HTTPIE_RICH_DEBUG is enabled."""
    if config.debug:
        print(f"[httpie-rich-terminal] {message}", file=sys.stderr)

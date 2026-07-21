"""Terminal identification and size probing.

This module only reads the environment and the tty; it knows nothing about
image protocols beyond naming which one a terminal speaks.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

from .config import Config


class ProtocolName:
    KITTY = "kitty"
    ITERM2 = "iterm2"


SKIP_TMUX = "tmux 环境，图片已跳过"
SKIP_UNSUPPORTED = "当前终端不支持内联图片显示"


@dataclass(frozen=True)
class Detection:
    protocol: Optional[str]
    terminal: str
    skip_reason: Optional[str]


def _is_kitty(env: Mapping[str, str]) -> bool:
    return env.get("TERM") == "xterm-kitty" or "KITTY_PID" in env


def _is_ghostty(env: Mapping[str, str]) -> bool:
    # TERM is unreliable here: Ghostty embedded in a host app reports
    # TERM=xterm-256color rather than xterm-ghostty.
    return env.get("TERM_PROGRAM") == "ghostty" or "GHOSTTY_RESOURCES_DIR" in env


def _is_iterm2(env: Mapping[str, str]) -> bool:
    # LC_TERMINAL survives ssh, TERM_PROGRAM does not.
    return env.get("TERM_PROGRAM") == "iTerm.app" or env.get("LC_TERMINAL") == "iTerm2"


def _is_wezterm(env: Mapping[str, str]) -> bool:
    return env.get("TERM_PROGRAM") == "WezTerm" or "WEZTERM_PANE" in env


def detect(config: Config, env: Optional[Mapping[str, str]] = None) -> Detection:
    """Resolve which image protocol to use, if any.

    A forced protocol outranks everything including tmux: it is the escape
    hatch for users who know what they are doing.
    """
    if env is None:
        env = os.environ

    if config.protocol is not None:
        return Detection(protocol=config.protocol, terminal="forced", skip_reason=None)

    if "TMUX" in env:
        return Detection(protocol=None, terminal="tmux", skip_reason=SKIP_TMUX)

    if _is_kitty(env):
        return Detection(protocol=ProtocolName.KITTY, terminal="kitty", skip_reason=None)
    if _is_ghostty(env):
        # Ghostty speaks the kitty protocol; it does not implement OSC 1337.
        return Detection(protocol=ProtocolName.KITTY, terminal="ghostty", skip_reason=None)
    if _is_iterm2(env):
        return Detection(protocol=ProtocolName.ITERM2, terminal="iterm2", skip_reason=None)
    if _is_wezterm(env):
        # WezTerm speaks both; OSC 1337 is the better-tested path there.
        return Detection(protocol=ProtocolName.ITERM2, terminal="wezterm", skip_reason=None)

    return Detection(protocol=None, terminal="unknown", skip_reason=SKIP_UNSUPPORTED)

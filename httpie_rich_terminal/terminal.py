"""Terminal identification and size probing.

This module only reads the environment and the tty; it knows nothing about
image protocols beyond naming which one a terminal speaks.
"""

import os
import struct
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

from .config import Config

try:
    import fcntl
    import termios

    _HAS_IOCTL = True
except ImportError:  # pragma: no cover - Windows has no fcntl/termios
    _HAS_IOCTL = False


class ProtocolName:
    KITTY = "kitty"
    ITERM2 = "iterm2"


SKIP_TMUX = "skipped inside tmux"
SKIP_UNSUPPORTED = "this terminal does not support inline images"


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


DEFAULT_COLUMNS = 80
DEFAULT_ROWS = 24


@dataclass(frozen=True)
class TerminalSize:
    columns: int
    rows: int
    cell_width: float
    cell_height: float

    @property
    def has_pixel_info(self) -> bool:
        """Whether pixel-accurate scaling is possible."""
        return self.cell_width > 0 and self.cell_height > 0


_UNKNOWN_SIZE = TerminalSize(
    columns=DEFAULT_COLUMNS, rows=DEFAULT_ROWS, cell_width=0.0, cell_height=0.0
)


def probe_size(fd: Optional[int] = None) -> TerminalSize:
    """Query the terminal geometry via TIOCGWINSZ.

    Falls back to an 80x24 grid with unknown cell pixels when the geometry
    cannot be determined. Resolving the file descriptor is inside the try
    because it fails in real deployments too: sys.__stdout__ is None under
    pythonw and detached daemons (AttributeError), and is a StringIO under
    pytest's capsys and various wrappers (io.UnsupportedOperation, a subclass
    of both OSError and ValueError). The ioctl itself raises OSError EINVAL /
    ENOTTY whenever stdout is not a TTY.
    """
    if not _HAS_IOCTL:
        return _UNKNOWN_SIZE

    try:
        if fd is None:
            fd = sys.__stdout__.fileno()
        packed = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8)
        rows, columns, x_pixels, y_pixels = struct.unpack("HHHH", packed)
    except (OSError, ValueError, AttributeError):
        return _UNKNOWN_SIZE

    if columns <= 0 or rows <= 0:
        return _UNKNOWN_SIZE

    cell_width = x_pixels / columns if x_pixels > 0 else 0.0
    cell_height = y_pixels / rows if y_pixels > 0 else 0.0
    return TerminalSize(
        columns=columns, rows=rows, cell_width=cell_width, cell_height=cell_height
    )

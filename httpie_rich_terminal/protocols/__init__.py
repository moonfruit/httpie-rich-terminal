"""Terminal image protocol implementations."""

from .base import ImageProtocol
from .iterm2 import ITerm2Protocol
from .kitty import KittyProtocol

# dict[str, ImageProtocol] rather than typing.Dict: ruff's UP006 rejects the
# latter, and PEP 585 subscripting is available from 3.9.
_PROTOCOLS: dict[str, ImageProtocol] = {
    KittyProtocol.name: KittyProtocol(),
    ITerm2Protocol.name: ITerm2Protocol(),
}


def get_protocol(name: str) -> ImageProtocol:
    """Look up a protocol implementation by its name.

    Raises KeyError for unknown names; callers resolve names through
    terminal.detect(), which only ever yields registered ones.
    """
    return _PROTOCOLS[name]


__all__ = ["ImageProtocol", "ITerm2Protocol", "KittyProtocol", "get_protocol"]

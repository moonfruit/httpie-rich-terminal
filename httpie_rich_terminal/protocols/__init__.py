"""Terminal image protocol implementations."""

from .base import ImageProtocol
from .kitty import KittyProtocol

__all__ = ["ImageProtocol", "KittyProtocol"]

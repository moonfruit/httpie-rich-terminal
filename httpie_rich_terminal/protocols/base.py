"""The protocol-layer contract.

Implementations turn image bytes into a terminal escape sequence. They take no
size arguments: scaling is done upstream in pixel terms, because both kitty's
c/r and iTerm2's width/height mean "occupy exactly N cells" and would upscale
small images.
"""

from abc import ABC, abstractmethod


class ImageProtocol(ABC):
    name = ""

    @abstractmethod
    def accepts_format(self, image_format: str) -> bool:
        """Whether this protocol can transmit the given Pillow format verbatim."""

    @abstractmethod
    def render(self, data: bytes, image_format: str) -> str:
        """Encode image bytes as an escape sequence ready to be written out."""

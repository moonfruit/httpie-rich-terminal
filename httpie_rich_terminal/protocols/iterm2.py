"""iTerm2 inline images protocol.

Spec: https://iterm2.com/documentation-images.html

    ESC ] 1337 ; File = <args> : <base64> ST

Also spoken by WezTerm. ST terminates the sequence instead of BEL to avoid
ringing the bell. No width/height is sent: scaling happens upstream in pixels,
and iTerm2 already shrinks oversized images to the window on its own.
"""

import base64

from .base import ImageProtocol

_OSC_START = "\x1b]1337;File="
_ST = "\x1b\\"

_ACCEPTED_FORMATS = frozenset({"PNG", "JPEG", "GIF"})


class ITerm2Protocol(ImageProtocol):
    name = "iterm2"

    def accepts_format(self, image_format: str) -> bool:
        return image_format.upper() in _ACCEPTED_FORMATS

    def render(self, data: bytes, image_format: str) -> str:
        encoded = base64.standard_b64encode(data).decode("ascii")
        # inline=1 is mandatory; without it iTerm2 downloads the file instead.
        args = f"inline=1;preserveAspectRatio=1;size={len(data)}"
        return f"{_OSC_START}{args}:{encoded}{_ST}\n"

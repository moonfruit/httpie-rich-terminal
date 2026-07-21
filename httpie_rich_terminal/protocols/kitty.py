"""kitty graphics protocol.

Spec: https://sw.kovidgoyal.net/kitty/graphics-protocol/

    ESC _ G <control data> ; <payload> ESC \\

Also spoken by Ghostty. Only PNG is transmitted (f=100); q=2 suppresses the
terminal's OK/error replies, which would otherwise pollute stdout.
"""

import base64

from .base import ImageProtocol

KITTY_CHUNK_SIZE = 4096

_APC_START = "\x1b_G"
_APC_END = "\x1b\\"


class KittyProtocol(ImageProtocol):
    name = "kitty"

    def accepts_format(self, image_format: str) -> bool:
        return image_format.upper() == "PNG"

    def render(self, data: bytes, image_format: str) -> str:
        encoded = base64.standard_b64encode(data).decode("ascii")
        chunks = [
            encoded[i : i + KITTY_CHUNK_SIZE]
            for i in range(0, len(encoded), KITTY_CHUNK_SIZE)
        ]
        if not chunks:
            chunks = [""]

        # A payload that lands exactly on the chunk boundary still needs an
        # explicit terminating sequence.
        if len(chunks[-1]) == KITTY_CHUNK_SIZE:
            chunks.append("")

        sequences: list = []
        for index, chunk in enumerate(chunks):
            is_last = index == len(chunks) - 1
            more = "0" if is_last else "1"
            if index == 0:
                control = f"a=T,f=100,q=2,m={more}"
            else:
                control = f"m={more}"
            sequences.append(f"{_APC_START}{control};{chunk}{_APC_END}")

        # Trailing newline keeps the shell prompt off the image.
        return "".join(sequences) + "\n"

"""MIME-to-renderer dispatch.

The extension point for future renderers: add a prefix mapping here and the
plugin picks it up. Text-oriented renderers will additionally need a
FormatterPlugin entry point declaring group_name = 'colors' — see section 2.4
of the design doc for why 'format' would break HTTPie's built-in formatters.
"""

from collections.abc import Callable
from typing import Optional

from .config import Config
from .renderers.image import render_image
from .terminal import Detection, TerminalSize

Renderer = Callable[[bytes, str, Detection, TerminalSize, Config], str]

_RENDERERS: dict[str, Renderer] = {
    "image/": render_image,
}


def find_renderer(mime: str) -> Optional[Renderer]:
    normalised = mime.lower()
    for prefix, renderer in _RENDERERS.items():
        if normalised.startswith(prefix):
            return renderer
    return None


def supports_mime(mime: str) -> bool:
    return find_renderer(mime) is not None

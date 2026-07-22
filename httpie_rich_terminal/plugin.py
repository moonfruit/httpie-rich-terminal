"""The HTTPie entry point — the only module that imports httpie.

HTTPie calls a ConverterPlugin only when the response body contains a NUL byte
and the output is a pretty stream. convert() returns the escape sequence as a
plain string, which flows through the formatter chain untouched as long as the
returned MIME is one pygments cannot claim.
"""

import re
import traceback

from httpie.plugins import ConverterPlugin

from .config import debug_log, load_config
from .registry import find_renderer, supports_mime
from .renderers.image import describe, format_summary
from .terminal import detect, probe_size

#: Returning image/* here would let downstream formatters rewrite the payload;
#: image/svg+xml is provably corrupted by XMLFormatter. Keep this private type.
OUTPUT_MIME = "application/x-httpie-rich-terminal"

#: Pillow embeds the repr of the stream it failed on, e.g.
#: "cannot identify image file <_io.BytesIO object at 0x105...>". The heap
#: address is noise in a user-facing line and differs on every run.
_OBJECT_REPR = re.compile(r"\s*<[\w.]+ object at 0x[0-9a-fA-F]+>")


def _clean_error(exc: Exception) -> str:
    """Render an exception for the summary line, without volatile object reprs."""
    return _OBJECT_REPR.sub("", str(exc)).strip() or type(exc).__name__


class RichTerminalConverter(ConverterPlugin):
    name = "rich-terminal"
    description = "Display image responses inline in the terminal"

    @classmethod
    def supports(cls, mime: str) -> bool:
        """Claim the body based on MIME alone.

        Terminal capability is deliberately not checked here: the fallback
        summary line needs the image dimensions, which requires decoding the
        body, and supports() has no access to it.
        """
        if load_config().disable:
            return False
        return supports_mime(mime)

    def convert(self, body: bytes) -> tuple[str, str]:
        # Everything lives inside the try, including the setup steps: this
        # method is the last line of defence and must never raise toward
        # HTTPie. Both seeds are chosen so the except branch still works if
        # setup is what failed -- describe(b"") yields a dimensionless
        # ImageInfo rather than raising.
        config = None
        data = b""
        try:
            config = load_config()
            # HTTPie hands us a bytearray; normalise so Pillow and slicing behave.
            data = bytes(body)
            renderer = find_renderer(self.mime)
            if renderer is None:
                return OUTPUT_MIME, self._summary(data, "no renderer for this type")

            detection = detect(config)
            debug_log(
                config,
                f"terminal={detection.terminal} protocol={detection.protocol}",
            )
            size = probe_size()
            debug_log(
                config,
                f"size={size.columns}x{size.rows} cell={size.cell_width}x{size.cell_height}",
            )
            return OUTPUT_MIME, renderer(data, self.mime, detection, size, config)
        except Exception as exc:
            if config is not None and config.debug:
                debug_log(config, "render failed:\n" + traceback.format_exc())
            return OUTPUT_MIME, self._summary(data, f"render failed: {_clean_error(exc)}")

    def _summary(self, data: bytes, reason: str) -> str:
        return format_summary(describe(data, self.mime), reason)

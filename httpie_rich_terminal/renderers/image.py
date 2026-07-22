"""Image rendering: scaling decisions and protocol hand-off."""

import io
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from ..config import Config, debug_log
from ..protocols import get_protocol
from ..protocols.base import ImageProtocol
from ..terminal import Detection, TerminalSize


def plan_resize(
    image_size: tuple[int, int], term: TerminalSize, config: Config
) -> Optional[tuple[int, int]]:
    """Return the target pixel size, or None when the image should be left alone.

    Returns None when the terminal did not report pixel geometry: without cell
    dimensions there is no way to convert a column budget into pixels, and
    guessing would risk upscaling.
    """
    if not term.has_pixel_info:
        return None

    max_columns = min(config.max_width or term.columns, term.columns)
    default_rows = max(1, term.rows // 2)
    max_rows = min(config.max_height or default_rows, term.rows)

    max_pixel_width = max_columns * term.cell_width
    max_pixel_height = max_rows * term.cell_height

    width, height = image_size
    if width <= 0 or height <= 0:
        return None

    scale = min(max_pixel_width / width, max_pixel_height / height)
    # Never enlarge: an image that already fits is passed through untouched.
    if scale >= 1.0:
        return None

    return (max(1, round(width * scale)), max(1, round(height * scale)))


@dataclass(frozen=True)
class ImageInfo:
    mime: str
    width: Optional[int]
    height: Optional[int]
    byte_size: int


def _human_size(byte_size: int) -> str:
    if byte_size < 1024:
        return f"{byte_size} B"
    if byte_size < 1024 * 1024:
        return f"{byte_size // 1024} KB"
    return f"{byte_size / (1024 * 1024):.1f} MB"


def describe(body: bytes, mime: str) -> ImageInfo:
    """Extract metadata for the summary line, tolerating undecodable bytes."""
    width = height = None
    try:
        with Image.open(io.BytesIO(body)) as image:
            width, height = image.size
    except Exception:
        pass
    return ImageInfo(mime=mime, width=width, height=height, byte_size=len(body))


def format_summary(info: ImageInfo, reason: str) -> str:
    size = _human_size(info.byte_size)
    if info.width is not None and info.height is not None:
        return f"[{info.mime} {info.width}×{info.height}, {size} — {reason}]\n"
    return f"[{info.mime} {size} — {reason}]\n"


def prepare_payload(
    body: bytes, protocol: ImageProtocol, term: TerminalSize, config: Config
) -> tuple[bytes, str]:
    """Return the bytes to transmit and their format.

    Pass the original bytes through when no resize is needed and the protocol
    accepts the format. Multi-frame images are also passed through -- even
    when oversized -- as long as the protocol accepts the format, since
    resizing would collapse the animation to a single frame; the protocols
    that accept GIF (iTerm2, WezTerm) shrink oversized images to the window
    themselves. Everything else is re-encoded as PNG. GIF animation therefore
    survives on iTerm2 regardless of size and collapses to its first frame on
    kitty, which never accepts GIF in the first place.
    """
    with Image.open(io.BytesIO(body)) as image:
        source_format = (image.format or "").upper()
        target_size = plan_resize(image.size, term, config)
        # Resizing collapses an animation to a single frame, so for multi-frame
        # images the choice is animation or exact sizing, not both. Prefer
        # animation: the protocols that accept GIF shrink oversized images to
        # the window on their own (kitty never gets here -- it rejects GIF, so
        # its frames still collapse into a still PNG below).
        animated = getattr(image, "n_frames", 1) > 1

        if protocol.accepts_format(source_format) and (target_size is None or animated):
            if animated and target_size is not None:
                debug_log(config, f"passing oversized {source_format} through to keep animation")
            else:
                debug_log(config, f"passing {source_format} through unmodified")
            return body, source_format

        # Convert before resizing: Pillow ignores the resample filter for P and
        # 1 modes, silently falling back to NEAREST.
        if image.mode not in ("RGB", "RGBA", "L"):
            image = image.convert("RGBA")

        if target_size is not None:
            debug_log(config, f"resizing {image.size} -> {target_size}")
            image = image.resize(target_size, Image.LANCZOS)
        else:
            debug_log(config, f"re-encoding {source_format} as PNG")

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue(), "PNG"


def render_image(
    body: bytes,
    mime: str,
    detection: Detection,
    term: TerminalSize,
    config: Config,
) -> str:
    """Render an image response, or a one-line summary when it cannot be shown.

    This function is not self-guarding: undecodable bytes, Pillow errors, and
    the like are allowed to raise. `RichTerminalConverter.convert()` is the
    layer that catches such failures and turns them into a summary line, so a
    caller that invokes this directly (e.g. scripts/demo.py) must decide for
    itself whether that guarantee is needed.
    """
    if detection.protocol is None:
        reason = detection.skip_reason or "cannot display"
        debug_log(config, f"skipping image: {reason}")
        return format_summary(describe(body, mime), reason)

    protocol = get_protocol(detection.protocol)
    data, image_format = prepare_payload(body, protocol, term, config)
    debug_log(config, f"rendering via {protocol.name} as {image_format}")
    return protocol.render(data, image_format)

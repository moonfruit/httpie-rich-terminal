"""Image rendering: scaling decisions and protocol hand-off."""

from typing import Optional

from ..config import Config
from ..terminal import TerminalSize


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

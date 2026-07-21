#!/usr/bin/env python
"""Render sample images in the current terminal.

CI cannot verify escape sequences actually draw anything, so this script is the
manual check. Run it inside iTerm2, Ghostty, kitty or WezTerm.
"""

import io
import sys

from PIL import Image

from httpie_rich_terminal.config import load_config
from httpie_rich_terminal.renderers.image import render_image
from httpie_rich_terminal.terminal import detect, probe_size


def make_image(size, colour, image_format):
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format=image_format)
    return buffer.getvalue()


def main():
    config = load_config()
    detection = detect(config)
    size = probe_size()

    print(f"terminal : {detection.terminal}")
    print(f"protocol : {detection.protocol or '(none — ' + str(detection.skip_reason) + ')'}")
    print(f"geometry : {size.columns}x{size.rows} cells, "
          f"cell {size.cell_width:.1f}x{size.cell_height:.1f} px, "
          f"pixel info {'yes' if size.has_pixel_info else 'NO — scaling disabled'}")
    print()

    samples = [
        (
            "small PNG 120x80 (should not be enlarged)",
            make_image((120, 80), "tomato", "PNG"),
            "image/png",
        ),
        (
            "large PNG 2400x1200 (should shrink to fit)",
            make_image((2400, 1200), "steelblue", "PNG"),
            "image/png",
        ),
        ("JPEG 400x300", make_image((400, 300), "seagreen", "JPEG"), "image/jpeg"),
        ("BMP 300x200 (converted to PNG)", make_image((300, 200), "goldenrod", "BMP"), "image/bmp"),
    ]

    for label, data, mime in samples:
        print(f"--- {label} ---")
        sys.stdout.write(render_image(data, mime, detection, size, config))
        sys.stdout.flush()
        print()


if __name__ == "__main__":
    main()

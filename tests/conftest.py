import io

import pytest
from PIL import Image, ImageDraw


def _encode(image: Image.Image, image_format: str) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.fixture
def png_bytes():
    """A 100x50 red PNG — small enough that no scaling is triggered."""
    return _encode(Image.new("RGB", (100, 50), "red"), "PNG")


@pytest.fixture
def large_png_bytes():
    """A 2000x1000 PNG — wide enough to force a downscale."""
    return _encode(Image.new("RGB", (2000, 1000), "blue"), "PNG")


@pytest.fixture
def jpeg_bytes():
    return _encode(Image.new("RGB", (100, 50), "green"), "JPEG")


@pytest.fixture
def bmp_bytes():
    return _encode(Image.new("RGB", (100, 50), "white"), "BMP")


@pytest.fixture
def cmyk_jpeg_bytes():
    """A CMYK JPEG — PNG cannot encode this mode, so it must be converted."""
    return _encode(Image.new("CMYK", (100, 50), (0, 255, 255, 0)), "JPEG")


@pytest.fixture
def animated_gif_bytes():
    """A genuinely 3-frame GIF, for verifying animation survives pass-through."""
    frames = []
    for offset, colour in enumerate(("red", "green", "blue")):
        frame = Image.new("RGB", (60, 40), "black")
        ImageDraw.Draw(frame).rectangle(
            [offset * 15, 0, offset * 15 + 14, 39], fill=colour
        )
        frames.append(frame.convert("P", palette=Image.ADAPTIVE))
    buffer = io.BytesIO()
    frames[0].save(
        buffer, format="GIF", save_all=True, append_images=frames[1:], duration=200
    )
    return buffer.getvalue()


@pytest.fixture
def gif_bytes():
    return _encode(Image.new("P", (100, 50), 3), "GIF")

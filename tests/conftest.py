import io

import pytest
from PIL import Image


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
def gif_bytes():
    return _encode(Image.new("P", (100, 50), 3), "GIF")

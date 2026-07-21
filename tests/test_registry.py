from httpie_rich_terminal.registry import find_renderer, supports_mime
from httpie_rich_terminal.renderers.image import render_image


def test_image_mimes_are_supported():
    for mime in ("image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"):
        assert supports_mime(mime) is True


def test_non_image_mimes_are_not_supported():
    for mime in ("application/json", "text/html", "application/octet-stream"):
        assert supports_mime(mime) is False


def test_mime_matching_is_case_insensitive():
    assert supports_mime("IMAGE/PNG") is True


def test_find_renderer_returns_the_image_renderer():
    assert find_renderer("image/png") is render_image


def test_find_renderer_returns_none_for_unknown_mime():
    assert find_renderer("application/json") is None

import base64
import io

import pytest
from PIL import Image

from httpie_rich_terminal.config import load_config
from httpie_rich_terminal.protocols import get_protocol
from httpie_rich_terminal.renderers.image import (
    ImageInfo,
    describe,
    format_summary,
    prepare_payload,
    render_image,
)
from httpie_rich_terminal.terminal import Detection, ProtocolName, TerminalSize

AUTO = load_config({})
TERM = TerminalSize(columns=80, rows=24, cell_width=8.0, cell_height=17.0)
NO_PIXELS = TerminalSize(columns=80, rows=24, cell_width=0.0, cell_height=0.0)
KITTY = get_protocol(ProtocolName.KITTY)
ITERM2 = get_protocol(ProtocolName.ITERM2)


def test_describe_extracts_dimensions(png_bytes):
    info = describe(png_bytes, "image/png")
    assert info == ImageInfo(
        mime="image/png", width=100, height=50, byte_size=len(png_bytes)
    )


def test_describe_survives_undecodable_bytes():
    info = describe(b"not an image at all", "image/png")
    assert info.width is None
    assert info.height is None
    assert info.byte_size == 19


def test_format_summary_includes_dimensions_and_reason():
    info = ImageInfo(mime="image/png", width=1920, height=1080, byte_size=250880)
    assert format_summary(info, "当前终端不支持内联图片显示") == (
        "[image/png 1920×1080, 245 KB — 当前终端不支持内联图片显示]\n"
    )


def test_format_summary_omits_dimensions_when_unknown():
    info = ImageInfo(mime="image/png", width=None, height=None, byte_size=2048)
    assert format_summary(info, "渲染失败") == "[image/png 2 KB — 渲染失败]\n"


def test_small_png_passes_through_untouched_on_kitty(png_bytes):
    data, image_format = prepare_payload(png_bytes, KITTY, TERM, AUTO)
    assert data is png_bytes
    assert image_format == "PNG"


def test_jpeg_is_converted_to_png_for_kitty(jpeg_bytes):
    data, image_format = prepare_payload(jpeg_bytes, KITTY, TERM, AUTO)
    assert image_format == "PNG"
    assert Image.open(io.BytesIO(data)).format == "PNG"


def test_jpeg_passes_through_on_iterm2(jpeg_bytes):
    data, image_format = prepare_payload(jpeg_bytes, ITERM2, TERM, AUTO)
    assert data is jpeg_bytes
    assert image_format == "JPEG"


def test_gif_passes_through_on_iterm2_so_animation_survives(gif_bytes):
    data, image_format = prepare_payload(gif_bytes, ITERM2, TERM, AUTO)
    assert data is gif_bytes
    assert image_format == "GIF"


def test_gif_becomes_png_on_kitty(gif_bytes):
    data, image_format = prepare_payload(gif_bytes, KITTY, TERM, AUTO)
    assert image_format == "PNG"
    assert Image.open(io.BytesIO(data)).format == "PNG"


def test_cmyk_jpeg_is_converted_to_a_writable_mode_for_kitty(cmyk_jpeg_bytes):
    # PNG cannot encode CMYK at all: without the mode conversion Pillow raises
    # OSError("cannot write mode CMYK as PNG") and the whole render fails.
    data, image_format = prepare_payload(cmyk_jpeg_bytes, KITTY, TERM, AUTO)

    assert image_format == "PNG"
    converted = Image.open(io.BytesIO(data))
    assert converted.format == "PNG"
    assert converted.mode in ("RGB", "RGBA")


def test_cmyk_jpeg_passes_through_on_iterm2(cmyk_jpeg_bytes):
    # iTerm2 decodes JPEG itself, so no conversion is needed and none happens.
    data, image_format = prepare_payload(cmyk_jpeg_bytes, ITERM2, TERM, AUTO)

    assert data is cmyk_jpeg_bytes
    assert image_format == "JPEG"


def test_animated_gif_keeps_every_frame_on_iterm2(animated_gif_bytes):
    data, image_format = prepare_payload(animated_gif_bytes, ITERM2, TERM, AUTO)

    assert data is animated_gif_bytes
    assert image_format == "GIF"
    assert Image.open(io.BytesIO(data)).n_frames == 3


def test_animated_gif_collapses_to_one_frame_on_kitty(animated_gif_bytes):
    # kitty's f=100 transfer is a still PNG, so animation cannot survive.
    data, image_format = prepare_payload(animated_gif_bytes, KITTY, TERM, AUTO)

    assert image_format == "PNG"
    assert getattr(Image.open(io.BytesIO(data)), "n_frames", 1) == 1


def test_bmp_is_converted_for_both_protocols(bmp_bytes):
    for protocol in (KITTY, ITERM2):
        data, image_format = prepare_payload(bmp_bytes, protocol, TERM, AUTO)
        assert image_format == "PNG"


def test_oversized_image_is_downscaled_and_reencoded(large_png_bytes):
    data, image_format = prepare_payload(large_png_bytes, KITTY, TERM, AUTO)
    assert image_format == "PNG"
    assert Image.open(io.BytesIO(data)).size == (408, 204)


def test_no_downscale_without_pixel_info(large_png_bytes):
    data, _ = prepare_payload(large_png_bytes, KITTY, NO_PIXELS, AUTO)
    assert data is large_png_bytes


def test_render_image_emits_a_kitty_sequence(png_bytes):
    detection = Detection(protocol=ProtocolName.KITTY, terminal="kitty", skip_reason=None)
    out = render_image(png_bytes, "image/png", detection, TERM, AUTO)
    assert out.startswith("\x1b_Ga=T,f=100,q=2,")
    assert base64.standard_b64encode(png_bytes).decode("ascii")[:64] in out


def test_render_image_emits_an_iterm2_sequence(png_bytes):
    detection = Detection(protocol=ProtocolName.ITERM2, terminal="iterm2", skip_reason=None)
    out = render_image(png_bytes, "image/png", detection, TERM, AUTO)
    assert out.startswith("\x1b]1337;File=inline=1;")


def test_render_image_returns_a_summary_when_the_terminal_is_unsupported(png_bytes):
    detection = Detection(
        protocol=None, terminal="unknown", skip_reason="当前终端不支持内联图片显示"
    )
    out = render_image(png_bytes, "image/png", detection, TERM, AUTO)
    assert out == f"[image/png 100×50, {len(png_bytes)} B — 当前终端不支持内联图片显示]\n"


def test_render_image_returns_a_summary_inside_tmux(png_bytes):
    detection = Detection(protocol=None, terminal="tmux", skip_reason="tmux 环境，图片已跳过")
    out = render_image(png_bytes, "image/png", detection, TERM, AUTO)
    assert "tmux 环境，图片已跳过" in out


@pytest.mark.parametrize(
    "byte_size,expected",
    [(512, "512 B"), (2048, "2 KB"), (250880, "245 KB"), (5 * 1024 * 1024, "5.0 MB")],
)
def test_human_readable_sizes(byte_size, expected):
    info = ImageInfo(mime="image/png", width=None, height=None, byte_size=byte_size)
    assert expected in format_summary(info, "x")

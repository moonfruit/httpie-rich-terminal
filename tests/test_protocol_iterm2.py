import base64

from httpie_rich_terminal.protocols.iterm2 import ITerm2Protocol

PROTO = ITerm2Protocol()


def test_accepts_png_jpeg_and_gif():
    assert PROTO.accepts_format("PNG") is True
    assert PROTO.accepts_format("JPEG") is True
    assert PROTO.accepts_format("GIF") is True


def test_rejects_formats_the_terminal_cannot_decode():
    assert PROTO.accepts_format("BMP") is False
    assert PROTO.accepts_format("TIFF") is False


def test_accepts_format_is_case_insensitive():
    assert PROTO.accepts_format("jpeg") is True


def test_renders_a_single_osc_sequence():
    data = b"hello world"
    encoded = base64.standard_b64encode(data).decode("ascii")

    out = PROTO.render(data, "PNG")

    assert out == (
        f"\x1b]1337;File=inline=1;preserveAspectRatio=1;size={len(data)}:{encoded}\x1b\\\n"
    )


def test_uses_st_terminator_not_bel():
    out = PROTO.render(b"x", "PNG")
    assert out.rstrip("\n").endswith("\x1b\\")
    assert "\x07" not in out


def test_declares_inline_so_iterm_does_not_download_the_file():
    assert "inline=1" in PROTO.render(b"x", "PNG")


def test_size_argument_reports_the_original_byte_count():
    data = b"\x00" * 1234
    assert f"size={len(data)}" in PROTO.render(data, "PNG")


def test_payload_round_trips():
    data = bytes(range(256))
    out = PROTO.render(data, "PNG")
    # Strip the trailing newline, then the two-character ST terminator.
    payload = out.rstrip("\n")[:-2].split(":", 1)[1]
    assert base64.standard_b64decode(payload) == data


def test_output_ends_with_a_newline():
    assert PROTO.render(b"x", "PNG").endswith("\n")


def test_get_protocol_resolves_registered_names():
    from httpie_rich_terminal.protocols import get_protocol
    from httpie_rich_terminal.terminal import ProtocolName

    assert get_protocol(ProtocolName.KITTY).name == "kitty"
    assert get_protocol(ProtocolName.ITERM2).name == "iterm2"

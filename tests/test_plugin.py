from httpie_rich_terminal.plugin import OUTPUT_MIME, RichTerminalConverter


def test_output_mime_is_the_private_type():
    # Returning image/* would let downstream formatters mangle the sequence;
    # image/svg+xml is provably destroyed by XMLFormatter. Do not change this.
    assert OUTPUT_MIME == "application/x-httpie-rich-terminal"


def test_supports_image_mimes(monkeypatch):
    monkeypatch.delenv("HTTPIE_RICH_DISABLE", raising=False)
    assert RichTerminalConverter.supports("image/png") is True


def test_does_not_support_non_image_mimes(monkeypatch):
    monkeypatch.delenv("HTTPIE_RICH_DISABLE", raising=False)
    assert RichTerminalConverter.supports("application/json") is False


def test_disable_env_var_makes_the_plugin_invisible(monkeypatch):
    monkeypatch.setenv("HTTPIE_RICH_DISABLE", "1")
    assert RichTerminalConverter.supports("image/png") is False


def test_convert_returns_the_private_mime_and_a_sequence(monkeypatch, png_bytes):
    monkeypatch.setenv("TERM", "xterm-kitty")
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("HTTPIE_RICH_PROTOCOL", raising=False)

    mime, body = RichTerminalConverter("image/png").convert(png_bytes)

    assert mime == OUTPUT_MIME
    assert isinstance(body, str)
    assert body.startswith("\x1b_G")


def test_convert_accepts_a_bytearray(monkeypatch, png_bytes):
    # HTTPie accumulates the body into a bytearray, not bytes.
    monkeypatch.setenv("TERM", "xterm-kitty")
    monkeypatch.delenv("TMUX", raising=False)

    mime, body = RichTerminalConverter("image/png").convert(bytearray(png_bytes))

    assert mime == OUTPUT_MIME
    assert body.startswith("\x1b_G")


def test_convert_returns_a_summary_on_an_unsupported_terminal(monkeypatch, png_bytes):
    monkeypatch.setenv("TERM", "xterm-256color")
    for var in ("TERM_PROGRAM", "KITTY_PID", "GHOSTTY_RESOURCES_DIR", "LC_TERMINAL",
                "WEZTERM_PANE", "TMUX", "HTTPIE_RICH_PROTOCOL"):
        monkeypatch.delenv(var, raising=False)

    mime, body = RichTerminalConverter("image/png").convert(png_bytes)

    assert mime == OUTPUT_MIME
    assert body == f"[image/png 100×50, {len(png_bytes)} B — 当前终端不支持内联图片显示]\n"


def test_convert_never_raises_on_corrupt_input(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-kitty")
    monkeypatch.delenv("TMUX", raising=False)

    mime, body = RichTerminalConverter("image/png").convert(b"definitely not an image")

    assert mime == OUTPUT_MIME
    assert "渲染失败" in body


def test_convert_never_raises_when_a_renderer_explodes(monkeypatch, png_bytes):
    from httpie_rich_terminal import plugin

    def boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(plugin, "find_renderer", lambda mime: boom)
    monkeypatch.setenv("TERM", "xterm-kitty")

    mime, body = RichTerminalConverter("image/png").convert(png_bytes)

    assert mime == OUTPUT_MIME
    assert "渲染失败" in body
    assert "kaboom" in body


def test_convert_returns_a_summary_when_no_renderer_matches(monkeypatch, png_bytes):
    from httpie_rich_terminal import plugin

    monkeypatch.setattr(plugin, "find_renderer", lambda mime: None)
    mime, body = RichTerminalConverter("image/png").convert(png_bytes)

    assert mime == OUTPUT_MIME
    assert "无法渲染" in body


def test_summary_does_not_leak_volatile_object_reprs(monkeypatch):
    # Pillow's decode error embeds "<_io.BytesIO object at 0x...>", whose heap
    # address changes every run and means nothing to the reader.
    monkeypatch.setenv("TERM", "xterm-kitty")

    _, body = RichTerminalConverter("image/png").convert(b"garbage")

    assert "0x" not in body
    assert "object at" not in body
    assert "渲染失败" in body


def test_convert_survives_a_failure_during_setup(monkeypatch, png_bytes):
    # load_config() runs before anything else; if even that raises, convert()
    # must still return rather than propagate.
    from httpie_rich_terminal import plugin

    def boom():
        raise RuntimeError("config exploded")

    monkeypatch.setattr(plugin, "load_config", boom)

    mime, body = RichTerminalConverter("image/png").convert(png_bytes)

    assert mime == OUTPUT_MIME
    assert "config exploded" in body


def test_debug_mode_reports_the_traceback(monkeypatch, capsys):
    monkeypatch.setenv("HTTPIE_RICH_DEBUG", "1")
    monkeypatch.setenv("TERM", "xterm-kitty")

    RichTerminalConverter("image/png").convert(b"garbage")

    assert "Traceback" in capsys.readouterr().err

"""Guards the foundational assumption: escape sequences survive HTTPie's
formatter chain untouched. See design doc section 2.3."""

import pytest
from httpie.cli.argtypes import PARSED_DEFAULT_FORMAT_OPTIONS
from httpie.context import Environment
from httpie.encoding import smart_encode
from httpie.output.formatters.colors import get_lexer
from httpie.output.processing import Formatting

from httpie_rich_terminal.plugin import OUTPUT_MIME, RichTerminalConverter

KITTY_SEQUENCE = "\x1b_Ga=T,f=100,q=2,m=0;iVBORw0KGgo=\x1b\\\n"
ITERM2_SEQUENCE = "\x1b]1337;File=inline=1;preserveAspectRatio=1;size=4:aGVsbA==\x1b\\\n"


@pytest.fixture
def formatting():
    """The full pretty chain: Headers, JSON, XML and Color formatters."""
    env = Environment()
    env.colors = 256
    return Formatting(
        groups=["format", "colors"],
        env=env,
        explicit_json=True,
        format_options=PARSED_DEFAULT_FORMAT_OPTIONS,
        color_scheme="auto",
    )


def test_pygments_does_not_claim_our_mime():
    # A claimed MIME means the body gets lexed and the escape codes destroyed.
    assert get_lexer(mime=OUTPUT_MIME, explicit_json=True, body="x") is None


@pytest.mark.parametrize("sequence", [KITTY_SEQUENCE, ITERM2_SEQUENCE])
def test_sequences_survive_the_formatter_chain(formatting, sequence):
    assert formatting.format_body(content=sequence, mime=OUTPUT_MIME) == sequence


@pytest.mark.parametrize("sequence", [KITTY_SEQUENCE, ITERM2_SEQUENCE])
def test_sequences_survive_encoding(formatting, sequence):
    formatted = formatting.format_body(content=sequence, mime=OUTPUT_MIME)
    assert smart_encode(formatted, "utf-8") == sequence.encode("utf-8")


def test_svg_mime_would_corrupt_the_payload(formatting):
    # Documents *why* OUTPUT_MIME must not be a real image type. If this test
    # ever starts failing, HTTPie changed and the constraint may have relaxed.
    assert formatting.format_body(content=KITTY_SEQUENCE, mime="image/svg+xml") != KITTY_SEQUENCE


def test_end_to_end_convert_output_survives_the_chain(formatting, monkeypatch, png_bytes):
    monkeypatch.setenv("TERM", "xterm-kitty")
    monkeypatch.delenv("TMUX", raising=False)

    mime, body = RichTerminalConverter("image/png").convert(png_bytes)
    assert mime == OUTPUT_MIME

    formatted = formatting.format_body(content=body, mime=mime)
    assert formatted == body
    assert smart_encode(formatted, "utf-8") == body.encode("utf-8")

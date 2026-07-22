[English](https://github.com/moonfruit/httpie-rich-terminal/blob/main/README.md) | [简体中文](https://github.com/moonfruit/httpie-rich-terminal/blob/main/README.zh-CN.md)

[![PyPI](https://img.shields.io/pypi/v/httpie-rich-terminal)](https://pypi.org/project/httpie-rich-terminal/)
[![CI](https://github.com/moonfruit/httpie-rich-terminal/actions/workflows/ci.yml/badge.svg)](https://github.com/moonfruit/httpie-rich-terminal/actions/workflows/ci.yml)

# httpie-rich-terminal

Display HTTPie's image responses directly in your terminal.

```bash
http https://httpbin.org/image/png
```

## Supported terminals

| Terminal | Protocol | Status |
|---|---|---|
| kitty | kitty graphics | Supported |
| Ghostty | kitty graphics | Supported |
| iTerm2 | OSC 1337 inline images | Supported |
| WezTerm | OSC 1337 inline images | Supported |
| Inside tmux | — | No image, prints a summary line |
| Other terminals | — | No image, prints a summary line |

## Install

```bash
httpie plugins install httpie-rich-terminal
```

If HTTPie was installed with pip, this also works:

```bash
pip install httpie-rich-terminal
```

## Usage

Works as soon as it is installed, no extra flags needed:

```bash
http https://httpbin.org/image/jpeg
```

When the image cannot be shown, the plugin prints a one-line summary explaining why:

```
[image/png 1920×1080, 245 KB — this terminal does not support inline images]
```

## Configuration

Everything is controlled through environment variables.

| Variable | Default | Description |
|---|---|---|
| `HTTPIE_RICH_DISABLE` | `0` | Set to `1` to fully disable the plugin and restore HTTPie's native binary notice |
| `HTTPIE_RICH_MAX_WIDTH` | terminal columns | Maximum columns the image may occupy |
| `HTTPIE_RICH_MAX_HEIGHT` | half the terminal rows | Maximum rows the image may occupy |
| `HTTPIE_RICH_PROTOCOL` | `auto` | Force a protocol: `kitty` or `iterm2` |
| `HTTPIE_RICH_DEBUG` | `0` | Set to `1` to print detection and scaling decisions to stderr |

## Behavior

**Small images are never enlarged.** An image that already fits the terminal's available area is displayed at its original size.

**Format conversion is automatic.** WebP, BMP, TIFF, AVIF and similar formats are converted to PNG before being displayed. GIF animation plays correctly on iTerm2 and WezTerm — even an oversized image is passed through untouched and shrunk to fit by the terminal itself, since resizing would collapse the animation to a single frame. On kitty and Ghostty only the first frame is shown, because the kitty graphics protocol's still-image transfer mode does not support animation.

**The plugin does not participate when output is piped.** With `http ... > file.png` or `http ... | other-cmd`, HTTPie streams the original bytes and the plugin is never invoked — the image data comes through complete and untouched.

## Known limitations

**Some terminals do not report pixel dimensions.** The plugin queries the terminal's pixel size via `ioctl(TIOCGWINSZ)` to compute scaling. A few terminals fill that field with zero, in which case the plugin cannot convert columns to pixels and skips scaling entirely, outputting the image at its original size — iTerm2 and WezTerm still automatically fit oversized images to the window, while kitty and Ghostty crop what doesn't fit. `HTTPIE_RICH_MAX_WIDTH` likewise has no effect in this situation. Use `HTTPIE_RICH_DEBUG=1` to confirm whether this path was taken.

**Images are not shown inside tmux.** tmux requires `allow-passthrough` along with protocol-specific wrapping, and behavior varies significantly across versions, so the current version simply skips rendering and prints a summary instead. If you have already enabled `allow-passthrough` and are willing to take the risk, you can use `HTTPIE_RICH_PROTOCOL` to force a protocol and bypass this check.

**Only active in pretty output mode.** This is a limitation of HTTPie's plugin mechanism: `--pretty=none`, `--download`, and non-TTY output never go through the converter path.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```

To manually verify rendering in a real terminal:

```bash
uv run python scripts/demo.py
```

## License

MIT

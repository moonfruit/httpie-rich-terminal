[English](README.md) | [简体中文](README.zh-CN.md)

[![PyPI](https://img.shields.io/pypi/v/httpie-rich-terminal)](https://pypi.org/project/httpie-rich-terminal/)
[![CI](https://github.com/moonfruit/httpie-rich-terminal/actions/workflows/ci.yml/badge.svg)](https://github.com/moonfruit/httpie-rich-terminal/actions/workflows/ci.yml)

# httpie-rich-terminal

在终端中直接显示 HTTPie 的图片响应。

```bash
http https://httpbin.org/image/png
```

## 支持的终端

| 终端 | 协议 | 状态 |
|---|---|---|
| kitty | kitty graphics | 支持 |
| Ghostty | kitty graphics | 支持 |
| iTerm2 | OSC 1337 inline images | 支持 |
| WezTerm | OSC 1337 inline images | 支持 |
| tmux 内 | — | 不显示图片，打印摘要行 |
| 其他终端 | — | 不显示图片，打印摘要行 |

## 安装

```bash
httpie plugins install httpie-rich-terminal
```

若 HTTPie 是用 pip 安装的，也可以：

```bash
pip install httpie-rich-terminal
```

## 使用

装好即生效，无需额外参数：

```bash
http https://httpbin.org/image/jpeg
```

图片显示不出来时，插件会打印一行摘要说明原因（程序实际输出的是英文，因此示例保持原样）：

```
[image/png 1920×1080, 245 KB — this terminal does not support inline images]
```

## 配置

全部通过环境变量控制。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HTTPIE_RICH_DISABLE` | `0` | 设为 `1` 完全禁用插件，恢复 HTTPie 原生的二进制提示 |
| `HTTPIE_RICH_MAX_WIDTH` | 终端列数 | 图片最多占用的列数 |
| `HTTPIE_RICH_MAX_HEIGHT` | 终端行数的一半 | 图片最多占用的行数 |
| `HTTPIE_RICH_PROTOCOL` | `auto` | 强制指定协议：`kitty` 或 `iterm2` |
| `HTTPIE_RICH_DEBUG` | `0` | 设为 `1` 将检测与缩放决策打印到 stderr |

## 行为说明

**图片不会被放大。** 小于终端可用区域的图片按原始尺寸显示。

**格式转换是自动的。** WebP、BMP、TIFF、AVIF 等格式会被转成 PNG 后显示。GIF 动画在 iTerm2 和 WezTerm 中可以正常播放——即使图片超出终端可用区域也会原样透传、由终端自行缩小显示，因为缩放会把动画塌缩成单帧；在 kitty 和 Ghostty 中只显示第一帧，因为 kitty 图形协议的静态传输模式不支持动画。

**管道输出时插件不参与。** `http ... > file.png` 或 `http ... | other-cmd` 时 HTTPie 走原始字节流，插件不会被调用，图片数据完整无损。

## 已知限制

**部分终端不上报像素尺寸。** 插件通过 `ioctl(TIOCGWINSZ)` 获取终端的像素尺寸来计算缩放。少数终端会把该字段填 0，此时插件无法换算列数与像素的关系，会跳过缩放按原始尺寸输出——iTerm2 和 WezTerm 会自动把超宽图片缩放适配窗口，kitty 和 Ghostty 则会裁切超出部分。`HTTPIE_RICH_MAX_WIDTH` 在这种情况下同样无法生效。用 `HTTPIE_RICH_DEBUG=1` 可以确认是否走到了这条路径。

**tmux 中不显示图片。** tmux 需要 `allow-passthrough` 配合各协议的特殊封装，各版本行为差异较大，当前版本选择直接跳过并打印摘要。若你已开启 `allow-passthrough` 并愿意自行承担风险，可以用 `HTTPIE_RICH_PROTOCOL` 强制指定协议绕过该检测。

**只在 pretty 输出模式下生效。** 这是 HTTPie 插件机制的限制：`--pretty=none`、`--download` 以及非 TTY 输出都不会走 converter 路径。

## 开发

```bash
uv sync
uv run pytest
uv run ruff check .
```

在真实终端里手动验证渲染效果：

```bash
uv run python scripts/demo.py
```

## 许可

MIT

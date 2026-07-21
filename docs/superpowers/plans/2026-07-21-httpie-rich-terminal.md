# httpie-rich-terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 HTTPie 实现一个插件，当 HTTP 响应体是图片时，在 iTerm2 / Ghostty / kitty / WezTerm 中直接内联显示。

**Architecture:** 单一 `ConverterPlugin` 入口。`convert()` 直接返回终端转义序列字符串（已实测可无损流过 HTTPie 的 formatter 链），无需 `sys.stdout.write` 副作用。内部分为四层单向依赖：`terminal`（环境检测，不知协议存在）→ `protocols`（字节转序列，不依赖 Pillow/httpie）→ `renderers`（图像决策）→ `plugin`（唯一依赖 httpie 的文件）。

**Tech Stack:** Python 3.9+、httpie>=3.2、Pillow>=9.0、uv + hatchling、pytest、ruff、GitHub Actions。

设计文档：`docs/superpowers/specs/2026-07-21-httpie-rich-terminal-design.md`

## Global Constraints

- 包名 `httpie-rich-terminal`，模块名 `httpie_rich_terminal`。
- 最低 Python 版本 **3.9**。不得使用 `match` 语句、`X | Y` 联合类型注解、`Self` 类型。类型注解一律用 `typing` 模块的 `Optional` / `Tuple` / `Dict` 等大写形式。
- `convert()` 返回的 MIME 必须**恒为** `application/x-httpie-rich-terminal`。回传 `image/svg+xml` 之类会被下游 XMLFormatter 破坏内容（spec 2.3 节实测表）。
- **任何异常都不得向 HTTPie 抛出。** `convert()` 整体包 try/except，出错返回摘要行。
- 环境变量前缀统一 `HTTPIE_RICH_`，共五个：`DISABLE`、`MAX_WIDTH`、`MAX_HEIGHT`、`PROTOCOL`、`DEBUG`。
- 第一版**不注册任何 FormatterPlugin**（规避 HTTPie `groupby` 覆盖内建 formatter 的坑，spec 2.4 节）。
- 协议层 `render()` **不接收任何尺寸参数**。缩放全部在 Pillow 层以像素为单位完成。
- 「小图永不放大」是硬规则，`scale` 计算必须含 `min(1.0, ...)`。
- 所有面向用户的文案（摘要行、README）用简体中文。代码注释与 commit message 用英文。
- 每个任务结束必须 commit。

---

## File Structure

| 文件 | 职责 |
|---|---|
| `pyproject.toml` | 包元数据、依赖、entry point、ruff/pytest 配置 |
| `httpie_rich_terminal/__init__.py` | 版本号与公开导出 |
| `httpie_rich_terminal/config.py` | 环境变量解析为 `Config`，debug 日志 |
| `httpie_rich_terminal/terminal.py` | 终端识别（`Detection`）+ 尺寸探测（`TerminalSize`） |
| `httpie_rich_terminal/protocols/base.py` | `ImageProtocol` 抽象接口 |
| `httpie_rich_terminal/protocols/kitty.py` | kitty graphics protocol |
| `httpie_rich_terminal/protocols/iterm2.py` | iTerm2 inline images protocol |
| `httpie_rich_terminal/renderers/base.py` | `RenderContext` 数据类 |
| `httpie_rich_terminal/renderers/image.py` | 缩放计算、编码策略、摘要行 |
| `httpie_rich_terminal/registry.py` | MIME → renderer 分发 |
| `httpie_rich_terminal/plugin.py` | `RichTerminalConverter`，唯一依赖 httpie |
| `tests/` | 与源码同构的单测 |
| `scripts/demo.py` | 真实终端手动验证 |
| `.github/workflows/ci.yml` | lint + 测试矩阵 |
| `.github/workflows/release.yml` | PyPI Trusted Publishing |

---

## Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `httpie_rich_terminal/__init__.py`
- Create: `tests/test_packaging.py`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: 无
- Produces: 可安装的包骨架；`httpie_rich_terminal.__version__: str`

- [ ] **Step 1: 写 pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "httpie-rich-terminal"
version = "0.1.0"
description = "在终端中内联显示 HTTPie 的图片响应，支持 iTerm2、Ghostty、kitty、WezTerm"
readme = "README.md"
requires-python = ">=3.9"
license = "MIT"
authors = [{ name = "moon", email = "dkmoonfruit@gmail.com" }]
keywords = ["httpie", "plugin", "terminal", "images", "kitty", "iterm2", "ghostty"]
classifiers = [
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Utilities",
]
dependencies = [
    "httpie>=3.2",
    "Pillow>=9.0",
]

[project.urls]
Homepage = "https://github.com/moon/httpie-rich-terminal"
Issues = "https://github.com/moon/httpie-rich-terminal/issues"

[project.entry-points."httpie.plugins.converter.v1"]
httpie_rich_terminal = "httpie_rich_terminal.plugin:RichTerminalConverter"

[dependency-groups]
dev = [
    "pytest>=7.0",
    "ruff>=0.6",
]

[tool.hatch.build.targets.wheel]
packages = ["httpie_rich_terminal"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 2: 写 `httpie_rich_terminal/__init__.py`**

```python
"""在终端中内联显示 HTTPie 的图片响应。"""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

- [ ] **Step 3: 写打包冒烟测试**

创建 `tests/test_packaging.py`：

```python
import httpie_rich_terminal


def test_version_is_exposed():
    assert httpie_rich_terminal.__version__ == "0.1.0"
```

- [ ] **Step 4: 建环境并运行测试**

```bash
uv sync
uv run pytest tests/test_packaging.py -v
```

Expected: 1 passed

- [ ] **Step 5: 写 CI workflow**

创建 `.github/workflows/ci.yml`：

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - name: Install
        run: uv sync --python ${{ matrix.python-version }}
      - name: Lint
        run: uv run ruff check .
      - name: Test
        run: uv run pytest -v
```

- [ ] **Step 6: 跑 lint 确认干净**

```bash
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml httpie_rich_terminal/ tests/ .github/
git commit -m "feat: scaffold package with hatchling, pytest and CI matrix"
```

**不要提交 `uv.lock`**，把它加入 `.gitignore`。这是一个库而非应用：依赖以范围声明（`httpie>=3.2`、`Pillow>=9.0`），CI 应当每次重新解析，以便上游破坏尽早暴露。此外，本机全局 uv 配置可能把 index 指向区域镜像，提交的 lock 会把该镜像固化进一个本该可移植的文件。

---

## Task 2: 配置层

**Files:**
- Create: `httpie_rich_terminal/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `Config` 冻结数据类，字段：`disable: bool`、`max_width: Optional[int]`、`max_height: Optional[int]`、`protocol: Optional[str]`、`debug: bool`
  - `load_config(env: Optional[Mapping[str, str]] = None) -> Config`
  - `debug_log(config: Config, message: str) -> None`

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_config.py`：

```python
from httpie_rich_terminal.config import Config, load_config


def test_defaults_when_env_is_empty():
    cfg = load_config({})
    assert cfg == Config(
        disable=False, max_width=None, max_height=None, protocol=None, debug=False
    )


def test_disable_accepts_truthy_values():
    for value in ("1", "true", "TRUE", "yes", "on"):
        assert load_config({"HTTPIE_RICH_DISABLE": value}).disable is True


def test_disable_accepts_falsy_values():
    for value in ("0", "false", "no", "off", ""):
        assert load_config({"HTTPIE_RICH_DISABLE": value}).disable is False


def test_max_width_and_height_parsed_as_int():
    cfg = load_config({"HTTPIE_RICH_MAX_WIDTH": "80", "HTTPIE_RICH_MAX_HEIGHT": "20"})
    assert cfg.max_width == 80
    assert cfg.max_height == 20


def test_invalid_int_falls_back_to_none():
    cfg = load_config({"HTTPIE_RICH_MAX_WIDTH": "abc"})
    assert cfg.max_width is None


def test_non_positive_int_falls_back_to_none():
    assert load_config({"HTTPIE_RICH_MAX_WIDTH": "0"}).max_width is None
    assert load_config({"HTTPIE_RICH_MAX_WIDTH": "-5"}).max_width is None


def test_protocol_normalised_and_validated():
    assert load_config({"HTTPIE_RICH_PROTOCOL": "KITTY"}).protocol == "kitty"
    assert load_config({"HTTPIE_RICH_PROTOCOL": "iterm2"}).protocol == "iterm2"
    assert load_config({"HTTPIE_RICH_PROTOCOL": "auto"}).protocol is None
    assert load_config({"HTTPIE_RICH_PROTOCOL": "bogus"}).protocol is None


def test_load_config_reads_os_environ_by_default(monkeypatch):
    monkeypatch.setenv("HTTPIE_RICH_DEBUG", "1")
    assert load_config().debug is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'httpie_rich_terminal.config'`

- [ ] **Step 3: 实现 config.py**

创建 `httpie_rich_terminal/config.py`：

```python
"""Environment-variable driven configuration.

ConverterPlugin has no access to HTTPie's CLI arguments (--format-options is
only passed to formatters), so environment variables are the only knob.
"""

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

ENV_PREFIX = "HTTPIE_RICH_"

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_VALID_PROTOCOLS = frozenset({"kitty", "iterm2"})


@dataclass(frozen=True)
class Config:
    disable: bool
    max_width: Optional[int]
    max_height: Optional[int]
    protocol: Optional[str]
    debug: bool


def _read_bool(env: Mapping[str, str], name: str) -> bool:
    return env.get(ENV_PREFIX + name, "").strip().lower() in _TRUTHY


def _read_positive_int(env: Mapping[str, str], name: str) -> Optional[int]:
    """Parse a positive int, falling back to None on any malformed input."""
    raw = env.get(ENV_PREFIX + name)
    if raw is None:
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        return None
    return value if value > 0 else None


def _read_protocol(env: Mapping[str, str]) -> Optional[str]:
    """Return a forced protocol name, or None for auto-detection."""
    raw = env.get(ENV_PREFIX + "PROTOCOL", "").strip().lower()
    return raw if raw in _VALID_PROTOCOLS else None


def load_config(env: Optional[Mapping[str, str]] = None) -> Config:
    if env is None:
        env = os.environ
    return Config(
        disable=_read_bool(env, "DISABLE"),
        max_width=_read_positive_int(env, "MAX_WIDTH"),
        max_height=_read_positive_int(env, "MAX_HEIGHT"),
        protocol=_read_protocol(env),
        debug=_read_bool(env, "DEBUG"),
    )


def debug_log(config: Config, message: str) -> None:
    """Write a diagnostic line to stderr when HTTPIE_RICH_DEBUG is enabled."""
    if config.debug:
        print(f"[httpie-rich-terminal] {message}", file=sys.stderr)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add httpie_rich_terminal/config.py tests/test_config.py
git commit -m "feat: add environment-variable configuration layer"
```

---

## Task 3: 终端识别

**Files:**
- Create: `httpie_rich_terminal/terminal.py`
- Create: `tests/test_terminal_detection.py`

**Interfaces:**
- Consumes: `Config` from `httpie_rich_terminal.config`
- Produces:
  - `ProtocolName` 常量类：`ProtocolName.KITTY == "kitty"`、`ProtocolName.ITERM2 == "iterm2"`
  - `Detection` 冻结数据类，字段：`protocol: Optional[str]`、`terminal: str`、`skip_reason: Optional[str]`
  - `detect(config: Config, env: Optional[Mapping[str, str]] = None) -> Detection`

**注意**：`skip_reason` 仅在 `protocol is None` 时非空，它会被直接嵌入用户可见的摘要行，因此是简体中文。

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_terminal_detection.py`：

```python
from httpie_rich_terminal.config import load_config
from httpie_rich_terminal.terminal import ProtocolName, detect

AUTO = load_config({})


def test_kitty_detected_by_term():
    d = detect(AUTO, {"TERM": "xterm-kitty"})
    assert d.protocol == ProtocolName.KITTY
    assert d.terminal == "kitty"
    assert d.skip_reason is None


def test_kitty_detected_by_pid_when_term_is_generic():
    d = detect(AUTO, {"TERM": "xterm-256color", "KITTY_PID": "42"})
    assert d.protocol == ProtocolName.KITTY


def test_ghostty_detected_by_term_program():
    d = detect(AUTO, {"TERM_PROGRAM": "ghostty"})
    assert d.protocol == ProtocolName.KITTY
    assert d.terminal == "ghostty"


def test_ghostty_detected_by_resources_dir_with_generic_term():
    # Real-world case: Ghostty embedded in a host app reports TERM=xterm-256color.
    d = detect(AUTO, {"TERM": "xterm-256color", "GHOSTTY_RESOURCES_DIR": "/opt/ghostty"})
    assert d.protocol == ProtocolName.KITTY
    assert d.terminal == "ghostty"


def test_iterm2_detected_by_term_program():
    d = detect(AUTO, {"TERM_PROGRAM": "iTerm.app"})
    assert d.protocol == ProtocolName.ITERM2
    assert d.terminal == "iterm2"


def test_iterm2_detected_over_ssh_via_lc_terminal():
    d = detect(AUTO, {"LC_TERMINAL": "iTerm2"})
    assert d.protocol == ProtocolName.ITERM2


def test_wezterm_uses_iterm2_protocol():
    d = detect(AUTO, {"TERM_PROGRAM": "WezTerm"})
    assert d.protocol == ProtocolName.ITERM2
    assert d.terminal == "wezterm"


def test_unknown_terminal_is_skipped_with_reason():
    d = detect(AUTO, {"TERM": "xterm-256color"})
    assert d.protocol is None
    assert d.terminal == "unknown"
    assert d.skip_reason == "当前终端不支持内联图片显示"


def test_tmux_is_skipped_even_on_a_capable_terminal():
    d = detect(AUTO, {"TMUX": "/tmp/tmux-501/default,123,0", "TERM": "xterm-kitty"})
    assert d.protocol is None
    assert d.terminal == "tmux"
    assert d.skip_reason == "tmux 环境，图片已跳过"


def test_forced_protocol_wins_over_tmux():
    # The forced protocol is an escape hatch and must outrank tmux detection.
    cfg = load_config({"HTTPIE_RICH_PROTOCOL": "kitty"})
    d = detect(cfg, {"TMUX": "/tmp/tmux-501/default,123,0"})
    assert d.protocol == ProtocolName.KITTY
    assert d.terminal == "forced"
    assert d.skip_reason is None


def test_forced_protocol_wins_over_detection():
    cfg = load_config({"HTTPIE_RICH_PROTOCOL": "iterm2"})
    d = detect(cfg, {"TERM": "xterm-kitty"})
    assert d.protocol == ProtocolName.ITERM2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_terminal_detection.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'httpie_rich_terminal.terminal'`

- [ ] **Step 3: 实现 terminal.py 的检测部分**

创建 `httpie_rich_terminal/terminal.py`：

```python
"""Terminal identification and size probing.

This module only reads the environment and the tty; it knows nothing about
image protocols beyond naming which one a terminal speaks.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

from .config import Config


class ProtocolName:
    KITTY = "kitty"
    ITERM2 = "iterm2"


SKIP_TMUX = "tmux 环境，图片已跳过"
SKIP_UNSUPPORTED = "当前终端不支持内联图片显示"


@dataclass(frozen=True)
class Detection:
    protocol: Optional[str]
    terminal: str
    skip_reason: Optional[str]


def _is_kitty(env: Mapping[str, str]) -> bool:
    return env.get("TERM") == "xterm-kitty" or "KITTY_PID" in env


def _is_ghostty(env: Mapping[str, str]) -> bool:
    # TERM is unreliable here: Ghostty embedded in a host app reports
    # TERM=xterm-256color rather than xterm-ghostty.
    return env.get("TERM_PROGRAM") == "ghostty" or "GHOSTTY_RESOURCES_DIR" in env


def _is_iterm2(env: Mapping[str, str]) -> bool:
    # LC_TERMINAL survives ssh, TERM_PROGRAM does not.
    return env.get("TERM_PROGRAM") == "iTerm.app" or env.get("LC_TERMINAL") == "iTerm2"


def _is_wezterm(env: Mapping[str, str]) -> bool:
    return env.get("TERM_PROGRAM") == "WezTerm" or "WEZTERM_PANE" in env


def detect(config: Config, env: Optional[Mapping[str, str]] = None) -> Detection:
    """Resolve which image protocol to use, if any.

    A forced protocol outranks everything including tmux: it is the escape
    hatch for users who know what they are doing.
    """
    if env is None:
        env = os.environ

    if config.protocol is not None:
        return Detection(protocol=config.protocol, terminal="forced", skip_reason=None)

    if "TMUX" in env:
        return Detection(protocol=None, terminal="tmux", skip_reason=SKIP_TMUX)

    if _is_kitty(env):
        return Detection(protocol=ProtocolName.KITTY, terminal="kitty", skip_reason=None)
    if _is_ghostty(env):
        # Ghostty speaks the kitty protocol; it does not implement OSC 1337.
        return Detection(protocol=ProtocolName.KITTY, terminal="ghostty", skip_reason=None)
    if _is_iterm2(env):
        return Detection(protocol=ProtocolName.ITERM2, terminal="iterm2", skip_reason=None)
    if _is_wezterm(env):
        # WezTerm speaks both; OSC 1337 is the better-tested path there.
        return Detection(protocol=ProtocolName.ITERM2, terminal="wezterm", skip_reason=None)

    return Detection(protocol=None, terminal="unknown", skip_reason=SKIP_UNSUPPORTED)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_terminal_detection.py -v
```

Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add httpie_rich_terminal/terminal.py tests/test_terminal_detection.py
git commit -m "feat: add terminal detection with forced-protocol escape hatch"
```

---

## Task 4: 终端尺寸探测

**Files:**
- Modify: `httpie_rich_terminal/terminal.py`（追加，不改动 Task 3 的内容）
- Create: `tests/test_terminal_size.py`

**Interfaces:**
- Consumes: 无（纯 stdlib）
- Produces:
  - `TerminalSize` 冻结数据类，字段：`columns: int`、`rows: int`、`cell_width: float`、`cell_height: float`
  - `TerminalSize.has_pixel_info` 属性 → `bool`，两个 cell 尺寸均 > 0 时为 True
  - `probe_size(fd: Optional[int] = None) -> TerminalSize`

**背景**：`ioctl` 在非 TTY 上抛 `OSError: [Errno 25] Inappropriate ioctl for device`（已实测），且部分终端把 `ws_xpixel` / `ws_ypixel` 填 0。两种情况都必须优雅降级。

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_terminal_size.py`：

```python
import io
import struct

import pytest

from httpie_rich_terminal import terminal
from httpie_rich_terminal.terminal import TerminalSize, probe_size


def test_has_pixel_info_true_when_both_cell_dims_known():
    assert TerminalSize(80, 24, 8.0, 17.0).has_pixel_info is True


def test_has_pixel_info_false_when_cell_dims_are_zero():
    assert TerminalSize(80, 24, 0.0, 0.0).has_pixel_info is False
    assert TerminalSize(80, 24, 8.0, 0.0).has_pixel_info is False


def test_probe_size_computes_cell_dimensions(monkeypatch):
    # rows=24 cols=80 xpixel=640 ypixel=408 -> cells are 8.0 x 17.0
    packed = struct.pack("HHHH", 24, 80, 640, 408)
    monkeypatch.setattr(terminal.fcntl, "ioctl", lambda *a, **kw: packed)

    size = probe_size(fd=1)

    assert size.columns == 80
    assert size.rows == 24
    assert size.cell_width == pytest.approx(8.0)
    assert size.cell_height == pytest.approx(17.0)
    assert size.has_pixel_info is True


def test_probe_size_degrades_when_pixel_fields_are_zero(monkeypatch):
    packed = struct.pack("HHHH", 24, 80, 0, 0)
    monkeypatch.setattr(terminal.fcntl, "ioctl", lambda *a, **kw: packed)

    size = probe_size(fd=1)

    assert size.columns == 80
    assert size.rows == 24
    assert size.has_pixel_info is False


def test_probe_size_degrades_when_ioctl_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError(25, "Inappropriate ioctl for device")

    monkeypatch.setattr(terminal.fcntl, "ioctl", boom)

    size = probe_size(fd=1)

    assert size.has_pixel_info is False
    assert size.columns > 0
    assert size.rows > 0


def test_probe_size_degrades_without_ioctl_support(monkeypatch):
    # Windows has no fcntl/termios; the module still imports and probe_size
    # must return a usable default rather than raising NameError.
    #
    # The names must be deleted too, not just the flag flipped. With them
    # still bound, removing the guard leaves this test green: fd=1 is not a
    # tty under pytest, so fcntl.ioctl raises OSError, which the existing
    # except clause swallows into the very same _UNKNOWN_SIZE this asserts.
    # Deleting them makes a missing guard surface as NameError, which is not
    # in the except clause and therefore fails the test.
    monkeypatch.setattr(terminal, "_HAS_IOCTL", False)
    monkeypatch.delattr(terminal, "fcntl", raising=False)
    monkeypatch.delattr(terminal, "termios", raising=False)

    size = probe_size(fd=1)

    assert size.has_pixel_info is False
    assert size.columns > 0
    assert size.rows > 0


def test_probe_size_degrades_when_stdout_is_none(monkeypatch):
    # pythonw and detached daemons leave sys.__stdout__ as None.
    monkeypatch.setattr(terminal.sys, "__stdout__", None)

    size = probe_size()

    assert size.has_pixel_info is False
    assert size.columns > 0


def test_probe_size_degrades_when_stdout_has_no_fileno(monkeypatch):
    # pytest's capsys and various wrappers replace stdout with a StringIO,
    # whose fileno() raises io.UnsupportedOperation.
    monkeypatch.setattr(terminal.sys, "__stdout__", io.StringIO())

    size = probe_size()

    assert size.has_pixel_info is False
    assert size.columns > 0


def test_probe_size_degrades_when_columns_are_zero(monkeypatch):
    # A zero column count would make max-width maths collapse; treat as unknown.
    packed = struct.pack("HHHH", 0, 0, 0, 0)
    monkeypatch.setattr(terminal.fcntl, "ioctl", lambda *a, **kw: packed)

    size = probe_size(fd=1)

    assert size.columns > 0
    assert size.rows > 0
    assert size.has_pixel_info is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_terminal_size.py -v
```

Expected: FAIL，`ImportError: cannot import name 'TerminalSize'`

- [ ] **Step 3: 在 terminal.py 追加实现**

在 `httpie_rich_terminal/terminal.py` 顶部的 import 区补上：

```python
import struct
import sys
```

以及紧随其后的条件导入。`fcntl` 与 `termios` 是 POSIX-only，Windows 上顶层导入会抛 `ImportError`，导致 HTTPie 在加载插件时 `warnings.warn` 并跳过——用户即使从不请求图片，每次执行 `http` 都会看到一条警告：

```python
try:
    import fcntl
    import termios

    _HAS_IOCTL = True
except ImportError:  # pragma: no cover - Windows has no fcntl/termios
    _HAS_IOCTL = False
```

在文件末尾追加：

```python
DEFAULT_COLUMNS = 80
DEFAULT_ROWS = 24


@dataclass(frozen=True)
class TerminalSize:
    columns: int
    rows: int
    cell_width: float
    cell_height: float

    @property
    def has_pixel_info(self) -> bool:
        """Whether pixel-accurate scaling is possible."""
        return self.cell_width > 0 and self.cell_height > 0


_UNKNOWN_SIZE = TerminalSize(
    columns=DEFAULT_COLUMNS, rows=DEFAULT_ROWS, cell_width=0.0, cell_height=0.0
)


def probe_size(fd: Optional[int] = None) -> TerminalSize:
    """Query the terminal geometry via TIOCGWINSZ.

    Falls back to an 80x24 grid with unknown cell pixels when the geometry
    cannot be determined. Resolving the file descriptor is inside the try
    because it fails in real deployments too: sys.__stdout__ is None under
    pythonw and detached daemons (AttributeError), and is a StringIO under
    pytest's capsys and various wrappers (io.UnsupportedOperation, a subclass
    of both OSError and ValueError). The ioctl itself raises OSError EINVAL /
    ENOTTY whenever stdout is not a TTY.
    """
    if not _HAS_IOCTL:
        return _UNKNOWN_SIZE

    try:
        if fd is None:
            fd = sys.__stdout__.fileno()
        packed = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8)
        rows, columns, x_pixels, y_pixels = struct.unpack("HHHH", packed)
    except (OSError, ValueError, AttributeError):
        return _UNKNOWN_SIZE

    if columns <= 0 or rows <= 0:
        return _UNKNOWN_SIZE

    cell_width = x_pixels / columns if x_pixels > 0 else 0.0
    cell_height = y_pixels / rows if y_pixels > 0 else 0.0
    return TerminalSize(
        columns=columns, rows=rows, cell_width=cell_width, cell_height=cell_height
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_terminal_size.py -v
```

Expected: 6 passed

- [ ] **Step 5: 跑全量测试确认没破坏 Task 3**

```bash
uv run pytest -v
```

Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add httpie_rich_terminal/terminal.py tests/test_terminal_size.py
git commit -m "feat: probe terminal geometry with graceful ioctl fallback"
```

---

## Task 5: 协议接口与 kitty 协议

**Files:**
- Create: `httpie_rich_terminal/protocols/__init__.py`
- Create: `httpie_rich_terminal/protocols/base.py`
- Create: `httpie_rich_terminal/protocols/kitty.py`
- Create: `tests/test_protocol_kitty.py`

**Interfaces:**
- Consumes: 无（本层不依赖 Pillow、httpie、terminal）
- Produces:
  - `ImageProtocol` 抽象基类：`name: str` 类属性、`accepts_format(self, image_format: str) -> bool`、`render(self, data: bytes, image_format: str) -> str`
  - `KittyProtocol` 实现类
  - `KITTY_CHUNK_SIZE == 4096`

**协议要点**：APC 序列 `ESC _ G <control> ; <payload> ESC \`。base64 后按 4096 字节切块，除末块外每块长度必须是 4 的倍数（4096 本身是 4 的倍数，天然满足）。首块带完整 control data 加 `m=1`，后续块只带 `m`，末块 `m=0` 且 payload 可空。`q=2` 抑制终端应答，否则 OK 响应会污染输出。

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_protocol_kitty.py`：

```python
import base64

from httpie_rich_terminal.protocols.kitty import KITTY_CHUNK_SIZE, KittyProtocol

PROTO = KittyProtocol()


def test_only_accepts_png():
    assert PROTO.accepts_format("PNG") is True
    assert PROTO.accepts_format("JPEG") is False
    assert PROTO.accepts_format("GIF") is False


def test_accepts_format_is_case_insensitive():
    assert PROTO.accepts_format("png") is True


def test_single_chunk_payload_is_one_escape_sequence():
    data = b"tiny"
    encoded = base64.standard_b64encode(data).decode("ascii")

    out = PROTO.render(data, "PNG")

    assert out == f"\x1b_Ga=T,f=100,q=2,m=0;{encoded}\x1b\\\n"


def test_multi_chunk_splits_on_the_4096_boundary():
    # Choose a size whose base64 form is exactly 2 chunks + a remainder.
    data = b"\xff" * 6000
    encoded = base64.standard_b64encode(data).decode("ascii")
    assert len(encoded) > KITTY_CHUNK_SIZE

    out = PROTO.render(data, "PNG")
    sequences = [s for s in out.rstrip("\n").split("\x1b\\") if s]

    # First sequence carries the full control data and m=1.
    assert sequences[0].startswith(f"\x1b_Ga=T,f=100,q=2,m=1;{encoded[:KITTY_CHUNK_SIZE]}")
    # Continuation sequences carry only m.
    assert sequences[1].startswith("\x1b_Gm=")
    assert "a=T" not in sequences[1]
    # The final sequence closes the transfer.
    assert sequences[-1].startswith("\x1b_Gm=0;")


def test_all_chunks_except_the_last_are_multiples_of_four():
    data = b"\xab" * 9000
    out = PROTO.render(data, "PNG")

    payloads = []
    for seq in out.rstrip("\n").split("\x1b\\"):
        if not seq:
            continue
        payloads.append(seq.split(";", 1)[1])

    for payload in payloads[:-1]:
        assert len(payload) % 4 == 0


def test_payload_reassembles_to_the_original_bytes():
    data = bytes(range(256)) * 40
    out = PROTO.render(data, "PNG")

    payloads = []
    for seq in out.rstrip("\n").split("\x1b\\"):
        if not seq:
            continue
        payloads.append(seq.split(";", 1)[1])

    assert base64.standard_b64decode("".join(payloads)) == data


def test_payload_of_exactly_one_chunk_boundary():
    # base64 of 3072 bytes is exactly 4096 chars -> one full chunk, then a
    # terminating empty chunk.
    data = b"\x01" * 3072
    encoded = base64.standard_b64encode(data).decode("ascii")
    assert len(encoded) == KITTY_CHUNK_SIZE

    out = PROTO.render(data, "PNG")
    sequences = [s for s in out.rstrip("\n").split("\x1b\\") if s]

    assert len(sequences) == 2
    assert sequences[0] == f"\x1b_Ga=T,f=100,q=2,m=1;{encoded}"
    assert sequences[1] == "\x1b_Gm=0;"


def test_output_ends_with_a_newline_so_the_prompt_is_not_glued_to_the_image():
    assert PROTO.render(b"x", "PNG").endswith("\n")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_protocol_kitty.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'httpie_rich_terminal.protocols'`

- [ ] **Step 3: 写协议接口**

创建 `httpie_rich_terminal/protocols/__init__.py`（Task 6 会再扩充这个文件加入 iTerm2 与注册表，此处只放 kitty）：

```python
"""Terminal image protocol implementations."""

from .base import ImageProtocol
from .kitty import KittyProtocol

__all__ = ["ImageProtocol", "KittyProtocol"]
```

创建 `httpie_rich_terminal/protocols/base.py`：

```python
"""The protocol-layer contract.

Implementations turn image bytes into a terminal escape sequence. They take no
size arguments: scaling is done upstream in pixel terms, because both kitty's
c/r and iTerm2's width/height mean "occupy exactly N cells" and would upscale
small images.
"""

from abc import ABC, abstractmethod


class ImageProtocol(ABC):
    name = ""

    @abstractmethod
    def accepts_format(self, image_format: str) -> bool:
        """Whether this protocol can transmit the given Pillow format verbatim."""

    @abstractmethod
    def render(self, data: bytes, image_format: str) -> str:
        """Encode image bytes as an escape sequence ready to be written out."""
```

- [ ] **Step 4: 实现 kitty 协议**

创建 `httpie_rich_terminal/protocols/kitty.py`：

```python
"""kitty graphics protocol.

Spec: https://sw.kovidgoyal.net/kitty/graphics-protocol/

    ESC _ G <control data> ; <payload> ESC \\

Also spoken by Ghostty. Only PNG is transmitted (f=100); q=2 suppresses the
terminal's OK/error replies, which would otherwise pollute stdout.
"""

import base64
from typing import List

from .base import ImageProtocol

KITTY_CHUNK_SIZE = 4096

_APC_START = "\x1b_G"
_APC_END = "\x1b\\"


class KittyProtocol(ImageProtocol):
    name = "kitty"

    def accepts_format(self, image_format: str) -> bool:
        return image_format.upper() == "PNG"

    def render(self, data: bytes, image_format: str) -> str:
        encoded = base64.standard_b64encode(data).decode("ascii")
        chunks = [
            encoded[i : i + KITTY_CHUNK_SIZE]
            for i in range(0, len(encoded), KITTY_CHUNK_SIZE)
        ]
        if not chunks:
            chunks = [""]

        # A payload that lands exactly on the chunk boundary still needs an
        # explicit terminating sequence.
        if len(chunks[-1]) == KITTY_CHUNK_SIZE:
            chunks.append("")

        sequences: List[str] = []
        for index, chunk in enumerate(chunks):
            is_last = index == len(chunks) - 1
            more = "0" if is_last else "1"
            if index == 0:
                control = f"a=T,f=100,q=2,m={more}"
            else:
                control = f"m={more}"
            sequences.append(f"{_APC_START}{control};{chunk}{_APC_END}")

        # Trailing newline keeps the shell prompt off the image.
        return "".join(sequences) + "\n"
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/test_protocol_kitty.py -v
```

Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add httpie_rich_terminal/protocols/ tests/test_protocol_kitty.py
git commit -m "feat: add kitty graphics protocol with chunked transfer"
```

---

## Task 6: iTerm2 协议

**Files:**
- Create: `httpie_rich_terminal/protocols/iterm2.py`
- Modify: `httpie_rich_terminal/protocols/__init__.py`
- Create: `tests/test_protocol_iterm2.py`

**Interfaces:**
- Consumes: `ImageProtocol` from `.base`
- Produces: `ITerm2Protocol` 实现类

**协议要点**：OSC 序列 `ESC ] 1337 ; File = <args> : <base64> ST`。用 `ST`（`ESC \`）而非 `BEL` 终结，避免响铃。`inline=1` 必须显式指定，否则 iTerm2 会当作文件下载。不传 `width`/`height`。

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_protocol_iterm2.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_protocol_iterm2.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'httpie_rich_terminal.protocols.iterm2'`

- [ ] **Step 3: 实现 iTerm2 协议**

创建 `httpie_rich_terminal/protocols/iterm2.py`：

```python
"""iTerm2 inline images protocol.

Spec: https://iterm2.com/documentation-images.html

    ESC ] 1337 ; File = <args> : <base64> ST

Also spoken by WezTerm. ST terminates the sequence instead of BEL to avoid
ringing the bell. No width/height is sent: scaling happens upstream in pixels,
and iTerm2 already shrinks oversized images to the window on its own.
"""

import base64

from .base import ImageProtocol

_OSC_START = "\x1b]1337;File="
_ST = "\x1b\\"

_ACCEPTED_FORMATS = frozenset({"PNG", "JPEG", "GIF"})


class ITerm2Protocol(ImageProtocol):
    name = "iterm2"

    def accepts_format(self, image_format: str) -> bool:
        return image_format.upper() in _ACCEPTED_FORMATS

    def render(self, data: bytes, image_format: str) -> str:
        encoded = base64.standard_b64encode(data).decode("ascii")
        # inline=1 is mandatory; without it iTerm2 downloads the file instead.
        args = f"inline=1;preserveAspectRatio=1;size={len(data)}"
        return f"{_OSC_START}{args}:{encoded}{_ST}\n"
```

- [ ] **Step 4: 补全 protocols/__init__.py**

将 `httpie_rich_terminal/protocols/__init__.py` 整体替换为：

```python
"""Terminal image protocol implementations."""

from typing import Dict

from .base import ImageProtocol
from .iterm2 import ITerm2Protocol
from .kitty import KittyProtocol

_PROTOCOLS: Dict[str, ImageProtocol] = {
    KittyProtocol.name: KittyProtocol(),
    ITerm2Protocol.name: ITerm2Protocol(),
}


def get_protocol(name: str) -> ImageProtocol:
    """Look up a protocol implementation by its name.

    Raises KeyError for unknown names; callers resolve names through
    terminal.detect(), which only ever yields registered ones.
    """
    return _PROTOCOLS[name]


__all__ = ["ImageProtocol", "ITerm2Protocol", "KittyProtocol", "get_protocol"]
```

- [ ] **Step 5: 为 get_protocol 补测试**

在 `tests/test_protocol_iterm2.py` 末尾追加：

```python
def test_get_protocol_resolves_registered_names():
    from httpie_rich_terminal.protocols import get_protocol
    from httpie_rich_terminal.terminal import ProtocolName

    assert get_protocol(ProtocolName.KITTY).name == "kitty"
    assert get_protocol(ProtocolName.ITERM2).name == "iterm2"
```

- [ ] **Step 6: 运行测试确认通过**

```bash
uv run pytest tests/test_protocol_iterm2.py -v
```

Expected: 10 passed

- [ ] **Step 7: Commit**

```bash
git add httpie_rich_terminal/protocols/ tests/test_protocol_iterm2.py
git commit -m "feat: add iTerm2 inline images protocol and protocol registry"
```

---

## Task 7: 缩放计算

**Files:**
- Create: `httpie_rich_terminal/renderers/__init__.py`
- Create: `httpie_rich_terminal/renderers/image.py`（仅缩放部分）
- Create: `tests/test_image_scaling.py`

**Interfaces:**
- Consumes: `Config`、`TerminalSize`
- Produces: `plan_resize(image_size: Tuple[int, int], term: TerminalSize, config: Config) -> Optional[Tuple[int, int]]`，返回 `None` 表示不缩放

**核心规则**：`scale = min(1.0, 上限宽 / 图宽, 上限高 / 图高)`。`min` 中的 `1.0` 是「小图永不放大」的实现。`term.has_pixel_info` 为假时直接返回 `None`。

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_image_scaling.py`：

```python
from httpie_rich_terminal.config import load_config
from httpie_rich_terminal.renderers.image import plan_resize
from httpie_rich_terminal.terminal import TerminalSize

AUTO = load_config({})
# 80 cols x 24 rows, 8x17 px cells -> 640 x 408 px viewport.
# Default height cap is rows // 2 = 12 rows = 204 px.
TERM = TerminalSize(columns=80, rows=24, cell_width=8.0, cell_height=17.0)


def test_small_image_is_never_upscaled():
    assert plan_resize((100, 50), TERM, AUTO) is None


def test_image_exactly_at_the_limit_is_not_resized():
    assert plan_resize((640, 204), TERM, AUTO) is None


def test_wide_image_is_scaled_down_preserving_aspect_ratio():
    # 1280x400 -> width cap 640 gives scale 0.5; height 400*0.5=200 <= 204 cap.
    assert plan_resize((1280, 400), TERM, AUTO) == (640, 200)


def test_tall_image_is_constrained_by_the_height_cap():
    # 400x816 -> height cap 204 gives scale 0.25.
    assert plan_resize((400, 816), TERM, AUTO) == (100, 204)


def test_the_tighter_of_the_two_caps_wins():
    # 1280x1632: width scale 0.5, height scale 0.125 -> height wins.
    assert plan_resize((1280, 1632), TERM, AUTO) == (160, 204)


def test_max_width_env_var_tightens_the_cap():
    cfg = load_config({"HTTPIE_RICH_MAX_WIDTH": "40"})  # 40 cols = 320 px
    assert plan_resize((640, 100), TERM, cfg) == (320, 50)


def test_max_height_env_var_tightens_the_cap():
    cfg = load_config({"HTTPIE_RICH_MAX_HEIGHT": "6"})  # 6 rows = 102 px
    assert plan_resize((100, 204), TERM, cfg) == (50, 102)


def test_max_width_cannot_exceed_the_real_terminal_width():
    cfg = load_config({"HTTPIE_RICH_MAX_WIDTH": "999"})
    # Still capped at 80 cols = 640 px, so a 1280px image halves.
    assert plan_resize((1280, 100), TERM, cfg) == (640, 50)


def test_returns_none_when_pixel_info_is_unavailable():
    unknown = TerminalSize(columns=80, rows=24, cell_width=0.0, cell_height=0.0)
    assert plan_resize((4000, 3000), unknown, AUTO) is None


def test_result_dimensions_are_never_zero():
    # An extremely wide, one-pixel-tall image must not round its height to 0.
    result = plan_resize((10000, 1), TERM, AUTO)
    assert result is not None
    assert result[0] >= 1
    assert result[1] >= 1


def test_height_cap_defaults_to_half_the_terminal_on_a_tiny_terminal():
    # rows=1 -> max(1, 1 // 2) == 1 row == 17 px, never 0.
    tiny = TerminalSize(columns=80, rows=1, cell_width=8.0, cell_height=17.0)
    result = plan_resize((800, 400), tiny, AUTO)
    assert result is not None
    assert result[1] <= 17
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_image_scaling.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'httpie_rich_terminal.renderers'`

- [ ] **Step 3: 实现缩放计算**

创建 `httpie_rich_terminal/renderers/__init__.py`：

```python
"""Content renderers."""
```

创建 `httpie_rich_terminal/renderers/image.py`：

```python
"""Image rendering: scaling decisions and protocol hand-off."""

from typing import Optional, Tuple

from ..config import Config
from ..terminal import TerminalSize


def plan_resize(
    image_size: Tuple[int, int], term: TerminalSize, config: Config
) -> Optional[Tuple[int, int]]:
    """Return the target pixel size, or None when the image should be left alone.

    Returns None when the terminal did not report pixel geometry: without cell
    dimensions there is no way to convert a column budget into pixels, and
    guessing would risk upscaling.
    """
    if not term.has_pixel_info:
        return None

    max_columns = min(config.max_width or term.columns, term.columns)
    default_rows = max(1, term.rows // 2)
    max_rows = min(config.max_height or default_rows, term.rows)

    max_pixel_width = max_columns * term.cell_width
    max_pixel_height = max_rows * term.cell_height

    width, height = image_size
    if width <= 0 or height <= 0:
        return None

    # The 1.0 term is what guarantees small images are never enlarged.
    scale = min(1.0, max_pixel_width / width, max_pixel_height / height)
    if scale >= 1.0:
        return None

    return (max(1, round(width * scale)), max(1, round(height * scale)))
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_image_scaling.py -v
```

Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add httpie_rich_terminal/renderers/ tests/test_image_scaling.py
git commit -m "feat: add pixel-accurate scaling with a never-upscale guarantee"
```

---

## Task 8: 图片渲染与摘要行

**Files:**
- Modify: `httpie_rich_terminal/renderers/image.py`（追加）
- Create: `tests/conftest.py`
- Create: `tests/test_image_render.py`

**Interfaces:**
- Consumes: `plan_resize`、`ImageProtocol`、`get_protocol`、`Detection`、`TerminalSize`、`Config`
- Produces:
  - `ImageInfo` 冻结数据类，字段：`mime: str`、`width: Optional[int]`、`height: Optional[int]`、`byte_size: int`
  - `describe(body: bytes, mime: str) -> ImageInfo`
  - `format_summary(info: ImageInfo, reason: str) -> str`
  - `prepare_payload(body: bytes, protocol: ImageProtocol, term: TerminalSize, config: Config) -> Tuple[bytes, str]`
  - `render_image(body: bytes, mime: str, detection: Detection, term: TerminalSize, config: Config) -> str`

**编码规则**（唯一一条）：无需缩放且协议接受该格式 → 原样透传；否则 Pillow 转 PNG。

**摘要行格式**：`[image/png 1920×1080, 245 KB — 当前终端不支持内联图片显示]`。尺寸不可知时退化为 `[image/png 245 KB — 原因]`。注意分隔符是 U+2014 em dash 和 U+00D7 multiplication sign。

- [ ] **Step 1: 写测试夹具**

创建 `tests/conftest.py`：

```python
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
```

- [ ] **Step 2: 写失败的测试**

创建 `tests/test_image_render.py`：

```python
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
    assert out == "[image/png 100×50, %d B — 当前终端不支持内联图片显示]\n" % len(png_bytes)


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
```

- [ ] **Step 3: 运行测试确认失败**

```bash
uv run pytest tests/test_image_render.py -v
```

Expected: FAIL，`ImportError: cannot import name 'ImageInfo'`

- [ ] **Step 4: 在 image.py 追加实现**

将 `httpie_rich_terminal/renderers/image.py` 顶部的整个 import 区**替换**为下面这段。注意 `..config` 与 `..terminal` 各自只能出现一行 import，否则 ruff 的 `I` 规则会报错：

```python
"""Image rendering: scaling decisions and protocol hand-off."""

import io
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image

from ..config import Config, debug_log
from ..protocols import get_protocol
from ..protocols.base import ImageProtocol
from ..terminal import Detection, TerminalSize
```

然后在文件末尾追加：

```python
@dataclass(frozen=True)
class ImageInfo:
    mime: str
    width: Optional[int]
    height: Optional[int]
    byte_size: int


def _human_size(byte_size: int) -> str:
    if byte_size < 1024:
        return f"{byte_size} B"
    if byte_size < 1024 * 1024:
        return f"{byte_size // 1024} KB"
    return f"{byte_size / (1024 * 1024):.1f} MB"


def describe(body: bytes, mime: str) -> ImageInfo:
    """Extract metadata for the summary line, tolerating undecodable bytes."""
    width = height = None
    try:
        with Image.open(io.BytesIO(body)) as image:
            width, height = image.size
    except Exception:
        pass
    return ImageInfo(mime=mime, width=width, height=height, byte_size=len(body))


def format_summary(info: ImageInfo, reason: str) -> str:
    size = _human_size(info.byte_size)
    if info.width is not None and info.height is not None:
        return f"[{info.mime} {info.width}×{info.height}, {size} — {reason}]\n"
    return f"[{info.mime} {size} — {reason}]\n"


def prepare_payload(
    body: bytes, protocol: ImageProtocol, term: TerminalSize, config: Config
) -> Tuple[bytes, str]:
    """Return the bytes to transmit and their format.

    One rule: pass the original bytes through when no resize is needed and the
    protocol accepts the format; otherwise re-encode as PNG. GIF animation
    survives on iTerm2 and collapses to its first frame on kitty purely as a
    consequence of that rule.
    """
    with Image.open(io.BytesIO(body)) as image:
        source_format = (image.format or "").upper()
        target_size = plan_resize(image.size, term, config)

        if target_size is None and protocol.accepts_format(source_format):
            debug_log(config, f"passing {source_format} through unmodified")
            return body, source_format

        if target_size is not None:
            debug_log(config, f"resizing {image.size} -> {target_size}")
            image = image.resize(target_size, Image.LANCZOS)
        else:
            debug_log(config, f"re-encoding {source_format} as PNG")

        if image.mode not in ("RGB", "RGBA", "L"):
            image = image.convert("RGBA")

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue(), "PNG"


def render_image(
    body: bytes,
    mime: str,
    detection: Detection,
    term: TerminalSize,
    config: Config,
) -> str:
    """Render an image response, or a one-line summary when it cannot be shown."""
    if detection.protocol is None:
        reason = detection.skip_reason or "无法显示"
        debug_log(config, f"skipping image: {reason}")
        return format_summary(describe(body, mime), reason)

    protocol = get_protocol(detection.protocol)
    data, image_format = prepare_payload(body, protocol, term, config)
    debug_log(config, f"rendering via {protocol.name} as {image_format}")
    return protocol.render(data, image_format)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/test_image_render.py -v
```

Expected: 20 passed

- [ ] **Step 6: 跑全量测试**

```bash
uv run pytest -v && uv run ruff check .
```

Expected: 全部通过，lint 干净

- [ ] **Step 7: Commit**

```bash
git add httpie_rich_terminal/renderers/image.py tests/conftest.py tests/test_image_render.py
git commit -m "feat: render images to escape sequences with summary-line fallback"
```

---

## Task 9: MIME 分发注册表

**Files:**
- Create: `httpie_rich_terminal/registry.py`
- Create: `tests/test_registry.py`

**Interfaces:**
- Consumes: `render_image`
- Produces:
  - `Renderer` 类型别名：`Callable[[bytes, str, Detection, TerminalSize, Config], str]`
  - `supports_mime(mime: str) -> bool`
  - `find_renderer(mime: str) -> Optional[Renderer]`

这一层存在的意义是为后续渲染器（Markdown、表格）留出扩展点：新增时只往 `_RENDERERS` 加一条前缀映射。

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_registry.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_registry.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'httpie_rich_terminal.registry'`

- [ ] **Step 3: 实现 registry.py**

创建 `httpie_rich_terminal/registry.py`：

```python
"""MIME-to-renderer dispatch.

The extension point for future renderers: add a prefix mapping here and the
plugin picks it up. Text-oriented renderers will additionally need a
FormatterPlugin entry point declaring group_name = 'colors' — see section 2.4
of the design doc for why 'format' would break HTTPie's built-in formatters.
"""

from typing import Callable, Dict, Optional

from .config import Config
from .renderers.image import render_image
from .terminal import Detection, TerminalSize

Renderer = Callable[[bytes, str, Detection, TerminalSize, Config], str]

_RENDERERS: Dict[str, Renderer] = {
    "image/": render_image,
}


def find_renderer(mime: str) -> Optional[Renderer]:
    normalised = mime.lower()
    for prefix, renderer in _RENDERERS.items():
        if normalised.startswith(prefix):
            return renderer
    return None


def supports_mime(mime: str) -> bool:
    return find_renderer(mime) is not None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_registry.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add httpie_rich_terminal/registry.py tests/test_registry.py
git commit -m "feat: add MIME dispatch registry as the renderer extension point"
```

---

## Task 10: HTTPie 插件入口

**Files:**
- Create: `httpie_rich_terminal/plugin.py`
- Create: `tests/test_plugin.py`

**Interfaces:**
- Consumes: `load_config`、`detect`、`probe_size`、`find_renderer`、`supports_mime`、`describe`、`format_summary`
- Produces:
  - `OUTPUT_MIME == "application/x-httpie-rich-terminal"`
  - `RichTerminalConverter(ConverterPlugin)`，实现 `supports(cls, mime)` 与 `convert(self, body)`

**关键约束**：

1. `convert()` 恒返回 `(OUTPUT_MIME, str)`。返回 `image/*` 会让下游 formatter 破坏内容。
2. `supports()` 只看 MIME 和 `DISABLE`，**不看终端能力**——摘要行需要图片元数据，而元数据必须解码 body 才有，`supports()` 拿不到 body。
3. `convert()` 内任何异常都必须吞掉并转为摘要行。
4. HTTPie 传进来的 `body` 是 `bytearray` 而非 `bytes`（`streams.py` 用 `bytearray()` 累积），实现需容忍。

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_plugin.py`：

```python
import pytest

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
    assert body == "[image/png 100×50, %d B — 当前终端不支持内联图片显示]\n" % len(png_bytes)


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


def test_debug_mode_reports_the_traceback(monkeypatch, capsys):
    monkeypatch.setenv("HTTPIE_RICH_DEBUG", "1")
    monkeypatch.setenv("TERM", "xterm-kitty")

    RichTerminalConverter("image/png").convert(b"garbage")

    assert "Traceback" in capsys.readouterr().err
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_plugin.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'httpie_rich_terminal.plugin'`

- [ ] **Step 3: 实现 plugin.py**

创建 `httpie_rich_terminal/plugin.py`：

```python
"""The HTTPie entry point — the only module that imports httpie.

HTTPie calls a ConverterPlugin only when the response body contains a NUL byte
and the output is a pretty stream. convert() returns the escape sequence as a
plain string, which flows through the formatter chain untouched as long as the
returned MIME is one pygments cannot claim.
"""

import traceback
from typing import Tuple

from httpie.plugins import ConverterPlugin

from .config import debug_log, load_config
from .registry import find_renderer, supports_mime
from .renderers.image import describe, format_summary
from .terminal import detect, probe_size

#: Returning image/* here would let downstream formatters rewrite the payload;
#: image/svg+xml is provably corrupted by XMLFormatter. Keep this private type.
OUTPUT_MIME = "application/x-httpie-rich-terminal"


class RichTerminalConverter(ConverterPlugin):
    name = "rich-terminal"
    description = "在终端中内联显示图片响应"

    @classmethod
    def supports(cls, mime: str) -> bool:
        """Claim the body based on MIME alone.

        Terminal capability is deliberately not checked here: the fallback
        summary line needs the image dimensions, which requires decoding the
        body, and supports() has no access to it.
        """
        if load_config().disable:
            return False
        return supports_mime(mime)

    def convert(self, body: bytes) -> Tuple[str, str]:
        config = load_config()
        # HTTPie hands us a bytearray; normalise so Pillow and slicing behave.
        data = bytes(body)
        try:
            renderer = find_renderer(self.mime)
            if renderer is None:
                return OUTPUT_MIME, self._summary(data, "无法渲染该类型")

            detection = detect(config)
            debug_log(
                config,
                f"terminal={detection.terminal} protocol={detection.protocol}",
            )
            size = probe_size()
            debug_log(
                config,
                f"size={size.columns}x{size.rows} cell={size.cell_width}x{size.cell_height}",
            )
            return OUTPUT_MIME, renderer(data, self.mime, detection, size, config)
        except Exception as exc:
            if config.debug:
                debug_log(config, "render failed:\n" + traceback.format_exc())
            return OUTPUT_MIME, self._summary(data, f"渲染失败：{exc}")

    def _summary(self, data: bytes, reason: str) -> str:
        return format_summary(describe(data, self.mime), reason)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_plugin.py -v
```

Expected: 11 passed

- [ ] **Step 5: 验证 HTTPie 真的能发现这个插件**

```bash
uv run python -c "
from httpie.plugins.registry import plugin_manager
from httpie.config import DEFAULT_CONFIG_DIR
plugin_manager.load_installed_plugins(None)
names = [c.__name__ for c in plugin_manager.get_converters()]
print('converters:', names)
assert 'RichTerminalConverter' in names, names
print('OK: plugin discovered via entry point')
"
```

Expected: 输出含 `RichTerminalConverter`，最后打印 `OK: plugin discovered via entry point`

- [ ] **Step 6: Commit**

```bash
git add httpie_rich_terminal/plugin.py tests/test_plugin.py
git commit -m "feat: add HTTPie ConverterPlugin entry point"
```

---

## Task 11: HTTPie 管道无损回归测试

**Files:**
- Create: `tests/test_httpie_pipeline.py`

**Interfaces:**
- Consumes: `OUTPUT_MIME`、`RichTerminalConverter`
- Produces: 无新接口，纯保护性测试

**为什么需要这个任务**：整个设计的地基是「`convert()` 返回的转义序列能无损流过 HTTPie 的 formatter 链」。这条性质依赖 `OUTPUT_MIME` 不被 pygments 认领。若将来有人把它改成 `image/svg+xml`，单测全绿但功能静默损坏。这个测试把 spec 2.3 节的实测固化下来。

- [ ] **Step 1: 写回归测试**

创建 `tests/test_httpie_pipeline.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认通过**

```bash
uv run pytest tests/test_httpie_pipeline.py -v
```

Expected: 8 passed

若 `test_svg_mime_would_corrupt_the_payload` 失败，说明 HTTPie 行为已变化，需重新核对设计文档 2.3 节，而不是删掉这个测试。

- [ ] **Step 3: 跑全量测试与 lint**

```bash
uv run pytest -v && uv run ruff check .
```

Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add tests/test_httpie_pipeline.py
git commit -m "test: pin the escape-sequence-survives-formatting invariant"
```

---

## Task 12: 文档、demo 脚本与发布配置

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `scripts/demo.py`
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: 全部已实现模块
- Produces: 可发布到 PyPI 的完整项目

- [ ] **Step 1: 写 README.md**

```markdown
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

图片显示不出来时，插件会打印一行摘要说明原因：

```
[image/png 1920×1080, 245 KB — 当前终端不支持内联图片显示]
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

**格式转换是自动的。** WebP、BMP、TIFF、AVIF 等格式会被转成 PNG 后显示。GIF 动画在 iTerm2 和 WezTerm 中可以正常播放；在 kitty 和 Ghostty 中只显示第一帧，因为 kitty 图形协议的静态传输模式不支持动画。

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
```

- [ ] **Step 2: 写 LICENSE**

创建 `LICENSE`：

```
MIT License

Copyright (c) 2026 moon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: 写 demo 脚本**

创建 `scripts/demo.py`：

```python
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
        ("small PNG 120x80 (should not be enlarged)", make_image((120, 80), "tomato", "PNG"), "image/png"),
        ("large PNG 2400x1200 (should shrink to fit)", make_image((2400, 1200), "steelblue", "PNG"), "image/png"),
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
```

- [ ] **Step 4: 在真实终端里跑 demo**

```bash
uv run python scripts/demo.py
```

Expected: 打印出终端检测信息，随后显示四张图片。**人工确认**：小图没有被放大、大图缩到了终端宽度内、四张图都能看见。

- [ ] **Step 5: 写发布 workflow**

创建 `.github/workflows/release.yml`：

```yaml
name: Release

on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Build
        run: uv build
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 6: 验证包能正常构建**

```bash
uv build && ls -1 dist/
```

Expected: 生成 `httpie_rich_terminal-0.1.0-py3-none-any.whl` 和 `.tar.gz`

- [ ] **Step 7: 跑全量测试与 lint 收尾**

```bash
uv run pytest -v && uv run ruff check .
```

Expected: 全部通过

- [ ] **Step 8: Commit**

```bash
git add README.md LICENSE scripts/ .github/workflows/release.yml
git commit -m "docs: add README, demo script and PyPI release workflow"
```

---

## 完成标准

全部任务完成后应满足：

- [ ] `uv run pytest` 全绿，覆盖终端检测、两个协议的字节级断言、缩放规则、编码策略、错误处理、HTTPie 管道无损性
- [ ] `uv run ruff check .` 无告警
- [ ] `uv run python scripts/demo.py` 在至少一个真实终端中正确显示图片
- [ ] `http https://httpbin.org/image/png` 在 iTerm2 或 kitty 或 Ghostty 中显示出图片
- [ ] `HTTPIE_RICH_DISABLE=1 http https://httpbin.org/image/png` 恢复 HTTPie 原生的二进制提示
- [ ] `uv build` 能产出 wheel 和 sdist

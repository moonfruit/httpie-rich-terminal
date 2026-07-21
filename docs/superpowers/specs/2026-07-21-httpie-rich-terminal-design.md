# httpie-rich-terminal 设计文档

日期：2026-07-21

## 1. 目标与范围

为 HTTPie 提供一个富终端渲染插件。第一版只实现一个功能：当 HTTP 响应体是图片时，在支持内联图片协议的终端里直接显示出来。

代码结构按「富终端渲染框架」组织，以便后续新增 Markdown、表格等渲染器时不改动核心。

**支持的终端**：iTerm2、Ghostty、kitty、WezTerm。

**明确不做的**（第一版）：

- tmux 内渲染图片（只打摘要行）
- sixel 协议（iTerm2 已有更好的原生协议，Ghostty 和 kitty 均明确拒绝支持 sixel，对目标终端零增量）
- kitty 动画帧传输
- 运行时终端能力查询

## 2. 背景：HTTPie 插件 API 的约束

以下结论基于 httpie 3.2.4 源码核对与实测，是本设计的地基。

### 2.1 图片只能走 ConverterPlugin

`FormatterPlugin` 不可行，有两个硬拦截：

1. `BufferedPrettyStream.iter_body` 发现 body 含 `b'\0'` 且没有匹配的 converter 时，直接 `raise BinarySuppressedError()`（`httpie/output/streams.py:244-247`）。formatter 根本不会被调用。
2. 即使绕过，`smart_decode` 使用 `content.decode(encoding, 'replace')`（`httpie/encoding.py:41`），二进制字节被替换为 U+FFFD，不可逆损坏。

因此必须由 `ConverterPlugin` 接住二进制响应体。

### 2.2 convert() 可以直接返回转义序列

`convert()` 返回的 `(new_mime, text)` 中，`new_mime` 会覆盖 `self.mime`，随后走 `process_body` → `format_body` → `smart_encode` 写出。终端转义序列是纯 ASCII 文本，可以原样作为返回值流过整条管道。

已实测验证（httpie 3.2.4，`--pretty=all` 等价的完整 formatter 链：HeadersFormatter、JSONFormatter、XMLFormatter、ColorFormatter）：

```
format_body 无损: True
smart_encode 无损: True
最终字节: b'\x1b_Ga=T,f=100,q=2,m=0;iVBORw0KGgo=\x1b\\\n'
```

因此**不需要** `sys.stdout.write` 副作用式的 hack（2017 年的 `banteg/httpie-image` 用的就是那种写法）。

### 2.3 返回的 mime 必须是自定义类型

`ColorFormatter.get_lexer_for_body` 对未知 mime 返回 `None`，body 原样放行（`httpie/output/formatters/colors.py:165-177`，无 TextLexer 兜底）。但若回传 `image/*` 中某些类型，下游 formatter 会改写内容。实测对照：

| 返回的 mime | 序列是否无损 |
|---|---|
| `application/x-httpie-rich-terminal` | 是 |
| `image/png` | 是 |
| `image/jpeg` | 是 |
| `image/svg+xml` | **否**（被 XML 处理破坏） |

因此 `convert()` 必须固定返回 `application/x-httpie-rich-terminal`。此约束需有回归测试保护。

### 2.4 不使用 FormatterPlugin 的额外收益

HTTPie 的 `PluginManager.get_formatters_grouped()` 用 `itertools.groupby` 分组，要求同 group 的插件在列表中连续。第三方 formatter 若声明 `group_name = 'format'`，会产生第二个 `'format'` 分组键，在字典推导中**覆盖掉内建的 HeadersFormatter/JSONFormatter/XMLFormatter**。

第一版不注册任何 formatter，完全规避此坑。将来新增文本类渲染器时需注意：必须使用 `group_name = 'colors'`。

### 2.5 插件不会被调用的场景

管道或重定向输出时，HTTPie 走 `RawStream` 直接输出原始字节，converter 不参与。此场景不在插件控制范围内，摘要行不会出现。

摘要行仅出现在两种情况：是 TTY 但终端不支持内联图片、以及 tmux 环境中。

## 3. 架构

```
httpie_rich_terminal/
├── __init__.py
├── plugin.py           # ConverterPlugin 入口（唯一 entry point）
├── registry.py         # MIME → Renderer 分发
├── config.py           # 环境变量读取
├── terminal.py         # 终端识别 + 尺寸探测（ioctl TIOCGWINSZ）
├── protocols/
│   ├── base.py         # ImageProtocol 接口
│   ├── kitty.py        # APC _G，f=100，4096 分块，q=2
│   └── iterm2.py       # OSC 1337 File=inline=1，ST 终结
└── renderers/
    ├── base.py         # Renderer 接口
    └── image.py        # Pillow 解码/缩放/编码 → 调 protocol
```

三层单向依赖，每层可独立测试：

- `terminal.py`：只读环境变量和 ioctl。不知道协议的存在。
- `protocols/`：只做「PNG 字节 + 目标尺寸 → 转义序列字符串」。不依赖 Pillow，不依赖 httpie。
- `renderers/image.py`：只做图像处理决策，通过 `ImageProtocol` 接口调用协议层。
- `plugin.py`：唯一依赖 httpie 的文件，约 40 行。

## 4. 数据流

```
httpie 检测到 body 含 \0
  → Conversion.get_converter('image/png')
  → RichTerminalConverter.supports()   ← 只检查 mime 是否为 image/* 且未被禁用
  → convert(body: bytes)
      → registry 按 mime 找到 ImageRenderer
      → Pillow 打开 → 决定是否缩放/转码 → 得到 PNG bytes + 目标列行数
      → protocol.render() → 转义序列 str
  → 返回 ('application/x-httpie-rich-terminal', 转义序列)
  → 流过 formatter 链 → smart_encode → 写出
```

`supports()` 与 `convert()` 的分工：

`supports()` 拿不到 body，只能看 MIME 和环境。因此它**不判断终端能力**，只判断两件事：MIME 是否为 `image/*`，以及 `HTTPIE_RICH_DISABLE` 是否为 `1`。

- `supports()` 返回 `False`（非图片 MIME 或插件被禁用）：插件完全隐形，HTTPie 打印它自己的 `NOTE: binary data not shown in terminal` 横幅。
- `supports()` 返回 `True`：body 交由 `convert()` 处理。终端能力的判断在 `convert()` 内部进行，因为摘要行需要图片元数据（尺寸、字节数），而这必须先用 Pillow 解码 body 才能得到。终端不支持、tmux、渲染失败三种情况均由 `convert()` 返回摘要行。

## 5. 终端识别

按优先级匹配，命中即停：

| 判据 | 结果 | 协议 |
|---|---|---|
| `HTTPIE_RICH_PROTOCOL` 已设置且非 `auto` | 强制 | 指定值 |
| `TMUX` 存在 | 降级摘要 | — |
| `TERM=xterm-kitty` 或 `KITTY_PID` 存在 | kitty | kitty |
| `TERM_PROGRAM=ghostty` 或 `GHOSTTY_BIN_DIR` 存在 | Ghostty | kitty |
| `TERM_PROGRAM=iTerm.app` 或 `LC_TERMINAL=iTerm2` | iTerm2 | iterm2 |
| `TERM_PROGRAM=WezTerm` 或 `WEZTERM_PANE` 存在 | WezTerm | iterm2 |
| 其他 | 未知 | 降级摘要 |

注意 `HTTPIE_RICH_PROTOCOL` 的优先级**高于 `TMUX` 检测**。这是有意的：它是逃生舱，用户显式指定协议时应当尊重该选择，即便身处 tmux（例如用户已开启 `allow-passthrough` 并愿意自担风险）。

`LC_TERMINAL` 一条使得 ssh 进远程主机时仍能识别 iTerm2（iTerm2 会透传该变量）。

**不做运行时 tty 查询**。运行时查询需要将终端切换到 raw mode 并等待响应，而 HTTPie 此时正在写输出流，风险不值当。误判时的逃生舱是 `HTTPIE_RICH_PROTOCOL`。

Ghostty 不支持 iTerm2 的 OSC 1337 协议，必须走 kitty 协议。WezTerm 两个协议都支持，选 iTerm2 协议因其兼容性更稳（WezTerm 的 kitty 协议实现与 kitty 本身有行为差异）。

## 6. 协议层

### 6.1 kitty graphics protocol

APC 序列格式：`ESC _ G <control data> ; <payload> ESC \`

直接传 PNG，控制键 `a=T,f=100,q=2`。`q=2` 抑制终端的 OK/错误应答，避免污染输出。

分块规则（硬性要求）：

- base64 编码后切块，每块不超过 4096 字节
- 除最后一块外，每块长度必须是 4 的倍数
- 首块携带完整 control data 加 `m=1`；后续块只带 `m`；末块 `m=0`，payload 可为空

```
\x1b_Ga=T,f=100,q=2,m=1;<chunk1>\x1b\\
\x1b_Gm=1;<chunk2>\x1b\\
\x1b_Gm=0;\x1b\\
```

尺寸控制用 `c`（列数）/ `r`（行数）。`f=100` 时不需要 `s`/`v`，终端从 PNG 头读取像素尺寸。

### 6.2 iTerm2 inline images protocol

OSC 序列格式：`ESC ] 1337 ; File = <args> : <base64> ST`

使用 `ST`（`ESC \`）而非 `BEL` 作为终结符，避免响铃。

参数：`inline=1`（必须显式指定，否则是下载而非内联）、`size=<字节数>`（用于进度显示）、`width=<N>` / `height=<N>`（单位为字符单元格）、`preserveAspectRatio=1`。

## 7. 缩放规则

1. `ioctl(TIOCGWINSZ)` 获取 `ws_col`、`ws_row`、`ws_xpixel`、`ws_ypixel`，计算单元格像素尺寸。
2. 上限列数 = `min(HTTPIE_RICH_MAX_WIDTH 或终端列数, 终端列数)`；上限行数 = `min(HTTPIE_RICH_MAX_HEIGHT 或 max(1, 终端行数 // 2), 终端行数)`。两者均为整数，除法取整。换算为像素上限。
3. `scale = min(1.0, 上限宽 / 图宽, 上限高 / 图高)`。`min` 中的 `1.0` 保证小图永不放大。
4. `scale < 1` 时用 Pillow LANCZOS 缩放。

`MAX_HEIGHT` 默认取终端行数的一半，理由是图片不应把整屏顶掉，需为响应头和后续 shell prompt 留出空间。

**降级分支**：若 `ws_xpixel` 或 `ws_ypixel` 为 0（部分终端不填充该字段），无法换算像素，则不做 Pillow 缩放，改为传递协议自带的单元格参数（iTerm2 `width=N`、kitty `c=N`）让终端自行缩放。此路径在 `HTTPIE_RICH_DEBUG=1` 时记录日志。

## 8. 编码策略

避免无谓的重编码：

| 情况 | 处理 |
|---|---|
| 原格式 PNG 且无需缩放 | 原始字节透传 |
| 原格式 JPEG 且无需缩放，协议为 iterm2 | 原始字节透传 |
| 原格式 JPEG 且无需缩放，协议为 kitty | 转 PNG（kitty `f=100` 只吃 PNG） |
| GIF 动画，协议为 iterm2 | 原始字节透传，动图可正常播放 |
| GIF 动画，协议为 kitty | 取首帧转 PNG |
| 其他格式（WebP/BMP/TIFF/AVIF 等）或需要缩放 | Pillow 转 PNG |

## 9. 配置

全部通过环境变量，前缀 `HTTPIE_RICH_`。`ConverterPlugin` 拿不到 HTTPie 的 CLI 参数（`--format-options` 只传给 formatter），故无法提供命令行选项。

| 变量 | 默认值 | 作用 |
|---|---|---|
| `HTTPIE_RICH_DISABLE` | `0` | 设为 `1` 时 `supports()` 直接返回 `False`，插件完全隐形 |
| `HTTPIE_RICH_MAX_WIDTH` | 终端列数 | 图片最大占用列数 |
| `HTTPIE_RICH_MAX_HEIGHT` | `max(1, 终端行数 // 2)` | 图片最大占用行数 |
| `HTTPIE_RICH_PROTOCOL` | `auto` | 取值 `kitty` / `iterm2` / `auto` |
| `HTTPIE_RICH_DEBUG` | `0` | 将检测结果、协议选择、缩放决策打印到 stderr |

数值型变量解析失败时回退到默认值，并在 debug 日志中记录，不抛异常。

## 10. 错误处理

**任何异常都不能让 HTTPie 崩溃**。`convert()` 整体包裹 try/except，捕获所有异常后返回摘要行加错误原因，绝不向上抛出。`HTTPIE_RICH_DEBUG=1` 时附带完整 traceback 到 stderr。

摘要行格式：

```
[image/png 1920×1080, 245 KB — 当前终端不支持内联图片显示]
[image/png 1920×1080, 245 KB — tmux 环境，图片已跳过]
[image/png — 渲染失败：<原因>]
```

若 Pillow 连解码都失败，尺寸信息不可得，则退化为只有 MIME 和字节数的形式。

## 11. 测试策略

- **终端检测**：用 `monkeypatch.setenv` 覆盖第 5 节表格的每一行，包含优先级冲突用例（如同时设置 `TMUX` 和 `KITTY_PID`）。
- **协议层**：给定固定 PNG 字节，逐字节断言输出的转义序列。重点覆盖 kitty 分块边界：payload 恰好 4096 字节、4097 字节、末块为空的情况。
- **缩放计算**：提取为纯函数，参数化测试。重点是「小图不放大」和 `xpixel=0` 的降级分支。
- **回归测试**：断言 `convert()` 返回的 mime 是 `application/x-httpie-rich-terminal`，并将返回值真正喂入 HTTPie 的 `Formatting` 链验证无损。此测试防止将来有人改回 `image/svg+xml` 一类会被下游破坏的 mime。
- **错误处理**：注入损坏的图片字节、Pillow 抛异常等场景，断言不抛出且返回摘要行。
- **端到端**：`scripts/demo.py` 手动执行，在真实终端中请求测试图片并渲染。CI 无法覆盖。
- **CI**：GitHub Actions，ruff lint 加 Python 3.9 至 3.13 矩阵。

## 12. 工程与发布

- 构建栈：`uv` 加 `hatchling`，`pyproject.toml` 采用 PEP 621。
- 最低 Python 版本：3.9。
- 运行时依赖：`httpie>=3.2`、`Pillow>=9.0`。
- entry point 声明：

  ```toml
  [project.entry-points."httpie.plugins.converter.v1"]
  httpie_rich_terminal = "httpie_rich_terminal.plugin:RichTerminalConverter"
  ```

- 发布：GitHub Actions 加 PyPI Trusted Publishing（OIDC，无需存储 token），打 tag 触发。

## 13. 后续扩展方向

不属于第一版范围，仅记录架构预留：

- 新增文本类渲染器（Markdown、表格）时，追加一个 `FormatterPlugin` 入口挂到同一个 `registry` 上，形成「两个入口，一套渲染器」。该 formatter 必须声明 `group_name = 'colors'`（见 2.4 节）。
- tmux 支持：协议层预留传输包裹接口，可后续补充 kitty Unicode placeholder（`U=1`）与 iTerm2 MultipartFile 两种方案。
- sixel 协议：若将来需覆盖 foot、Konsole、Windows Terminal 等终端再考虑。

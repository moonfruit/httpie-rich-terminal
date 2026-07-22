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

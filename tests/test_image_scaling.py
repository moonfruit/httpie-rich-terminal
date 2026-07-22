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


def test_max_height_cannot_exceed_the_real_terminal_height():
    cfg = load_config({"HTTPIE_RICH_MAX_HEIGHT": "999"})
    # Still capped at 24 rows = 408 px, so an 816px-tall image halves.
    assert plan_resize((100, 816), TERM, cfg) == (50, 408)


def test_degenerate_image_dimensions_are_rejected():
    assert plan_resize((0, 0), TERM, AUTO) is None
    assert plan_resize((100, 0), TERM, AUTO) is None
    assert plan_resize((-5, 10), TERM, AUTO) is None


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

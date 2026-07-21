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

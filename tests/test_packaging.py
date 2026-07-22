from importlib.metadata import entry_points, version

import httpie_rich_terminal
from httpie_rich_terminal.plugin import RichTerminalConverter

ENTRY_POINT_GROUP = "httpie.plugins.converter.v1"


def test_installed_version_matches_the_package():
    # dynamic version: pyproject reads __version__, so a drift means the
    # installed distribution and the module disagree.
    assert version("httpie-rich-terminal") == httpie_rich_terminal.__version__


def test_entry_point_resolves_to_the_converter():
    # The single most load-bearing line in pyproject.toml. A rename or typo
    # here makes the plugin invisible to HTTPie while every other test passes.
    points = entry_points(group=ENTRY_POINT_GROUP)
    loaded = [point.load() for point in points]
    assert RichTerminalConverter in loaded

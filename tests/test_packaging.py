from importlib.metadata import entry_points, version

import httpie_rich_terminal
from httpie_rich_terminal.plugin import RichTerminalConverter

ENTRY_POINT_GROUP = "httpie.plugins.converter.v1"


def test_installed_version_matches_the_package():
    # dynamic version: pyproject reads __version__, so a drift means the
    # installed distribution and the module disagree.
    assert version("httpie-rich-terminal") == httpie_rich_terminal.__version__


def _entry_points_in_group(group):
    """Select entry points by group across Python versions.

    entry_points(group=...) and the .select() API both arrived in 3.10; on 3.9
    entry_points() returns a plain dict keyed by group.
    """
    points = entry_points()
    if hasattr(points, "select"):
        return points.select(group=group)
    return points.get(group, [])


def test_entry_point_resolves_to_the_converter():
    # The single most load-bearing line in pyproject.toml. A rename or typo
    # here makes the plugin invisible to HTTPie while every other test passes.
    loaded = [point.load() for point in _entry_points_in_group(ENTRY_POINT_GROUP)]
    assert RichTerminalConverter in loaded

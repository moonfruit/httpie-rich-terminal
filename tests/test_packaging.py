import httpie_rich_terminal


def test_version_is_exposed():
    assert httpie_rich_terminal.__version__ == "0.1.0"

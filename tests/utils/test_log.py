from cmk_dev_site.utils.log import colorize


def test_colorize():
    assert colorize("test", "blue") == "\033[34mtest\033[0m"
    assert colorize("test", "red") == "\033[31mtest\033[0m"
    assert colorize("test", "unknown") == "test"

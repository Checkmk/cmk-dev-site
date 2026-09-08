from cmk_dev_site.utils.cli import resolve_argv

PROCESS_ARGV = ["-n", "foo"]


def test_resolve_argv_keeps_an_explicitly_empty_argv() -> None:
    assert resolve_argv([], PROCESS_ARGV) == []


def test_resolve_argv_keeps_given_arguments() -> None:
    assert resolve_argv(["2.3", "--edition", "cee"], PROCESS_ARGV) == ["2.3", "--edition", "cee"]


def test_resolve_argv_falls_back_only_for_none() -> None:
    assert resolve_argv(None, PROCESS_ARGV) == PROCESS_ARGV

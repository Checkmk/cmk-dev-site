import pytest

from cmk_dev_site import cmk_dev_install_site
from cmk_dev_site.cmk_dev_install import ExitCode, InstallResult
from cmk_dev_site.cmk_dev_install_site import core, install_args, site_args
from cmk_dev_site.omd import Edition


def test_install_args_forwards_version_and_edition() -> None:
    assert list(install_args("2.3", Edition.OLD_ENTERPRISE, "-v")) == [
        "2.3",
        "--edition",
        "cee",
        "-v",
    ]


def test_site_args_with_resolved_version() -> None:
    assert list(site_args("2.3.0-2026.07.10.cee", None, 0, "", None)) == [
        "2.3.0-2026.07.10.cee",
        "-f",
    ]


def test_site_args_appends_edition_suffix() -> None:
    assert list(site_args("3.0.0-2026-06-29", Edition.ULTIMATE, 0, "", None)) == [
        "3.0.0-2026-06-29.ultimate",
        "-f",
    ]


def test_site_args_without_version() -> None:
    assert list(site_args(None, None, 2, "-v", "mysite")) == [
        "--distributed",
        "2",
        "--name",
        "mysite",
        "-f",
        "-v",
    ]


def test_core_forwards_resolved_version_to_site(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The site step must use the version resolved by cmk-dev-install
    (e.g. "2.3" -> "2.3.0-2026.07.10.cee"), not the raw user input."""
    seen: dict[str, list[str]] = {}

    def fake_install(args: list[str]) -> InstallResult:
        seen["install"] = args
        return InstallResult(ExitCode.SUCCESS, "2.3.0-2026.07.10.cee")

    def fake_site(args: list[str]) -> int:
        seen["site"] = args
        return 0

    monkeypatch.setattr(cmk_dev_install_site, "cmk_dev_install", fake_install)
    monkeypatch.setattr(cmk_dev_install_site, "cmk_dev_site", fake_site)

    result = core(
        "2.3",
        None,
        site_distributed=0,
        site_name=None,
        dryrun=False,
        verbose=0,
        quiet=0,
    )

    assert result == 0
    assert seen["install"] == ["2.3"]
    assert seen["site"] == ["2.3.0-2026.07.10.cee", "-f"]
    assert "cmk-dev-site 2.3.0-2026.07.10.cee -f" in capsys.readouterr().out


def test_core_dryrun_does_not_execute(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(_args: list[str]) -> int:
        raise AssertionError("must not be called in dryrun")

    monkeypatch.setattr(cmk_dev_install_site, "cmk_dev_install", fail)
    monkeypatch.setattr(cmk_dev_install_site, "cmk_dev_site", fail)

    result = core(
        "2.3",
        None,
        site_distributed=0,
        site_name=None,
        dryrun=True,
        verbose=0,
        quiet=0,
    )

    assert result == 0
    out = capsys.readouterr().out
    assert "cmk-dev-install 2.3" in out
    # the site command depends on the version cmk-dev-install would resolve,
    # so it cannot be previewed without actually running the install step
    assert "cmk-dev-site" not in out

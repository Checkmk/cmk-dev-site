"""Tests for cmk_dev_relay module."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest import MonkeyPatch

from cmk_dev_site.cmk_dev_relay import get_site_name, get_version
from cmk_dev_site.relay.site import Site


def test_get_site_name_from_env() -> None:
    with patch.dict(os.environ, {"SITE": "test_site"}):
        assert get_site_name() == Site("test_site")


def test_get_site_name_from_site_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    site_file = tmp_path / ".site"
    site_file.write_text("site_from_file\n")

    # Change to the temp directory
    monkeypatch.chdir(tmp_path)

    # Ensure SITE env var is not set
    with patch.dict(os.environ, {}, clear=True):
        assert get_site_name() == Site("site_from_file")


def test_get_site_name_from_parent_site_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    site_file = tmp_path / ".site"
    site_file.write_text("parent_site\n")

    child_dir = tmp_path / "child" / "subdir"
    child_dir.mkdir(parents=True)
    monkeypatch.chdir(child_dir)

    # Ensure SITE env var is not set
    with patch.dict(os.environ, {}, clear=True):
        assert get_site_name() == Site("parent_site")


def test_get_site_name_from_omd_command(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Test getting site name from omd sites --bare command."""
    monkeypatch.chdir(tmp_path)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "omd_site\nanother_site\n"

    with (
        patch.dict(os.environ, {}, clear=True),
        patch("subprocess.run", return_value=mock_result) as mock_run,
    ):
        result = get_site_name()

        mock_run.assert_called_once_with(
            ["omd", "sites", "--bare"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert str(result) == "omd_site"


def test_get_site_name_omd_no_sites(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""

    with (
        patch.dict(os.environ, {}, clear=True),
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="Could not determine site name"),
    ):
        get_site_name()


def test_get_site_name_omd_command_not_found(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with (
        patch.dict(os.environ, {}, clear=True),
        patch("subprocess.run", side_effect=FileNotFoundError),
        pytest.raises(RuntimeError, match="Could not determine site name"),
    ):
        get_site_name()


def test_get_site_name_omd_command_fails(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with (
        patch.dict(os.environ, {}, clear=True),
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="Could not determine site name"),
    ):
        get_site_name()


def test_get_site_name_priority_env_over_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    site_file = tmp_path / ".site"
    site_file.write_text("file_site\n")

    monkeypatch.chdir(tmp_path)

    with patch.dict(os.environ, {"SITE": "env_site"}):
        assert get_site_name() == Site("env_site")


def test_get_version_ultimate() -> None:
    """Test parsing version from ultimate build."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "OMD - Open Monitoring Distribution Version 2.5.0-2025.12.22.ultimate"

    with patch("subprocess.run", return_value=mock_result):
        assert str(get_version(Site("test_site"))) == "2.5.0-2025.12.22"


def test_get_version_enterprise() -> None:
    """Test parsing version from enterprise build."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "OMD - Open Monitoring Distribution Version 2.3.0p1"

    with patch("subprocess.run", return_value=mock_result):
        assert str(get_version(Site("test_site"))) == "2.3.0p1"


def test_get_version_with_date() -> None:
    """Test parsing version with date suffix."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "OMD - Open Monitoring Distribution Version 2.4.0-2024.11.15.cee"

    with patch("subprocess.run", return_value=mock_result):
        assert str(get_version(Site("test_site"))) == "2.4.0-2024.11.15"


def test_get_version_invalid_output() -> None:
    """Test error handling for invalid omd version output."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Invalid output"

    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="Could not parse version"),
    ):
        get_version(Site("test_site"))

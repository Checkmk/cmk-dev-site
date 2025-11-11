from datetime import datetime
from unittest.mock import MagicMock

import pytest

from cmk_dev_site.cmk_dev_install import (
    CMK_DOWNLOAD_URL,
    TSBUILD_URL,
    find_last_release,
    parse_version,
)
from cmk_dev_site.omd import (
    BaseVersion,
    Edition,
    VersionWithPatch,
    VersionWithReleaseDate,
)


def test_parse_version():
    assert parse_version("2.3.0") == BaseVersion(2, 3, 0)
    parsed_version = parse_version("2.3.0p1")
    assert isinstance(parsed_version, VersionWithPatch)
    assert parsed_version.base_version == BaseVersion(2, 3, 0)
    assert parsed_version.patch_type == "p"
    assert parsed_version.patch == 1


def _mock_list_versions_with_date_side_effect(cmk_dates: list[str], tst_dates: list[str]):
    def list_versions_with_date_side_effect(
        url: str, _: BaseVersion
    ) -> list[VersionWithReleaseDate]:
        cmk_versions = [
            VersionWithReleaseDate(BaseVersion(2, 5, 0), datetime.strptime(d, "%Y.%m.%d").date())
            for d in cmk_dates
        ]
        tst_versions = [
            VersionWithReleaseDate(BaseVersion(2, 5, 0), datetime.strptime(d, "%Y.%m.%d").date())
            for d in tst_dates
        ]
        if url == CMK_DOWNLOAD_URL:
            return cmk_versions
        if url == TSBUILD_URL:
            return tst_versions
        return []

    return list_versions_with_date_side_effect


@pytest.mark.parametrize(
    "download_urls,cmk_dates,tst_dates,expected_version",
    [
        pytest.param(
            [CMK_DOWNLOAD_URL, TSBUILD_URL],
            ["2025.11.06", "2025.11.07", "2025.11.08", "2025.11.09", "2025.11.10", "2025.11.11"],
            ["2025.11.09", "2025.11.10", "2025.11.11"],
            "2.5.0-2025.11.11",
            id="both_available",
        ),
        pytest.param(
            [CMK_DOWNLOAD_URL],
            ["2025.11.06", "2025.11.07", "2025.11.08", "2025.11.09", "2025.11.10", "2025.11.11"],
            [],
            "2.5.0-2025.11.11",
            id="only_cmk_available",
        ),
        pytest.param(
            [TSBUILD_URL],
            [],
            ["2025.11.09", "2025.11.10", "2025.11.11"],
            "2.5.0-2025.11.11",
            id="only_tst_available_no_cmk",
        ),
        pytest.param(
            [TSBUILD_URL],
            [],
            [],
            RuntimeError,
            id="No package available",
        ),
    ],
)
def test_find_last_release(
    download_urls: list[str],
    cmk_dates: list[str],
    tst_dates: list[str],
    expected_version: str | type[RuntimeError],
):
    mock_file_server = MagicMock()

    mock_file_server.list_versions_with_date.side_effect = (
        _mock_list_versions_with_date_side_effect(cmk_dates, tst_dates)
    )
    mock_file_server.url_exists.return_value = True

    if expected_version is RuntimeError:
        with pytest.raises(RuntimeError):
            find_last_release(
                download_urls=download_urls,
                file_server=mock_file_server,
                base_version=BaseVersion(2, 5, 0),
                edition=Edition.PRO,
                distro_codename="jammy",
            )
    else:
        result = find_last_release(
            download_urls=download_urls,
            file_server=mock_file_server,
            base_version=BaseVersion(2, 5, 0),
            edition=Edition.PRO,
            distro_codename="jammy",
        )

        assert str(result.version) == expected_version

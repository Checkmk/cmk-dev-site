import pytest
from cmk_dev_site.cmk_dev_install import parse_version
from cmk_dev_site.omd import BaseVersion, VersionWithPatch


def test_parse_version():
    assert parse_version("2.3.0") == BaseVersion(2, 3, 0)
    parsed_version = parse_version("2.3.0p1")
    assert isinstance(parsed_version, VersionWithPatch)
    assert parsed_version.base_version == BaseVersion(2, 3, 0)
    assert parsed_version.patch_type == "p"
    assert parsed_version.patch == 1

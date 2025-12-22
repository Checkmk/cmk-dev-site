from datetime import date

from cmk_dev_site.cmk_dev_site import Config
from cmk_dev_site.omd import BaseVersion, VersionWithPatch, VersionWithReleaseDate


def test_default_name_base_version():
    version = BaseVersion(2, 3, 0)
    assert Config._default_name(version) == "v230"


def test_default_name_version_with_patch():
    version = VersionWithPatch(BaseVersion(2, 3, 0), "p", 1)
    assert Config._default_name(version) == "v230p1"


def test_default_name_version_with_release_date():
    version = VersionWithReleaseDate(BaseVersion(2, 3, 0), date(2025, 1, 1))
    assert Config._default_name(version) == "v230"

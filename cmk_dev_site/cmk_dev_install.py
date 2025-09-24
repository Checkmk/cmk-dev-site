"""cmk-dev-install

Download and install a Checkmk version.

If the version is already installed, it will only be downloaded and installed again if
the "-f" flag is used and no site is running on that version. Either way, the version
will be made the default OMD version. This is done to ease the follow-up use of
`cmk-dev-site`, which will by default use the default OMD version to create sites.

Depending on the specified version, the script looks in the following locations:
    https://download.checkmk.com/checkmk
    https://tstbuilds-artifacts.lan.tribe29.com
The script expects credentials to be stored in ~/.cmk-credentials file in the format
user:password (please follow the instructions https://wiki.lan.checkmk.net/x/aYUuBg)
"""

import argparse
import getpass
import hashlib
import http.client
import json
import logging
import re
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests

from .omd import (
    BaseVersion,
    CMKPackage,
    Edition,
    GitVersion,
    PartialVersion,
    Version,
    VersionWithPatch,
    VersionWithReleaseDate,
)
from .utils import run_command as run_command_c
from .utils.log import colorize, generate_log_decorator, get_logger
from .version import __version__

logger = get_logger(__name__)
log = generate_log_decorator(logger)

CREDENTIALS_FILE = Path("~/.cmk-credentials").expanduser()
CONFIG_PATH = Path("~/.config/jenkins_jobs/jenkins_jobs.ini").expanduser()
INSTALLATION_PATH = Path("/omd/versions")
TSBUILD_URL = "https://tstbuilds-artifacts.lan.tribe29.com"
CMK_DOWNLOAD_URL = "https://download.checkmk.com/checkmk"
DOWNLOAD_DIR = Path("/tmp")


def run_command(
    args: Sequence[str],
    check: bool = True,
    error_message: str | None = None,
    raise_runtime_error: bool = True,
    text: bool = True,
    silent: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    return run_command_c(
        args,
        check=check,
        error_message=error_message,
        raise_runtime_error=raise_runtime_error,
        text=text,
        silent=silent,
        logger=logger,  # slightly hackish: pass in the right logger
        **kwargs,
    )


def build_download_url(url: str, pkg: CMKPackage) -> str:
    """
    Generate the download URL for a given package.
    """
    return f"{url}/{pkg.version}/{pkg.package_name}"


@log()
def remove_package(pkg_name: str, installed_path: Path) -> None:
    """
    Remove a package using apt.
    """
    run_command(
        [
            "sudo",
            "apt-get",
            "purge",
            "-y",
            pkg_name,
        ],
        raise_runtime_error=False,
    )
    # making sure the path is relative to /omd/versions/
    if not installed_path.is_relative_to(INSTALLATION_PATH):
        raise RuntimeError(f"ERROR: Removing package failed: {installed_path} is not a valid path")
    run_command(
        [
            "sudo",
            "rm",
            "-rf",
            str(installed_path),
        ],
    )


@log()
def install_package(pkg_path: Path) -> None:
    """
    Install a package using apt from the provided file path.
    """
    run_command(
        [
            "sudo",
            "apt-get",
            "install",
            "-y",
            str(pkg_path),
        ],
        error_message="Failed to install package",
    )


def get_user_pass() -> tuple[str, str]:
    """Get the user and password from the credentials file"""

    try:
        user, password = CREDENTIALS_FILE.read_text(encoding="utf-8").strip().split(":", 1)
        return (user, password)
    except Exception as e:
        raise RuntimeError(
            f"ERROR: Credentials file not found or is not in a correct format: {CREDENTIALS_FILE}"
            ", please follow the instructions https://wiki.lan.checkmk.net/x/aYUuBg"
        ) from e


@dataclass
class DistroVersionInfo:
    version_id: str
    version_codename: str


def get_distro_version_info() -> DistroVersionInfo:
    """Get the distribution version ID and codename for Ubuntu."""
    data = dict(
        line.split("=", 1)
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    if data.get("ID") == "ubuntu" and {"VERSION_ID", "VERSION_CODENAME"} <= data.keys():
        return DistroVersionInfo(
            version_id=data["VERSION_ID"].strip('"'),
            version_codename=data["VERSION_CODENAME"].strip('"'),
        )
    raise RuntimeError("ERROR: Unsupported distribution or missing version info.")


def parse_version(
    version: str,
) -> Version:
    """Parse the version string into a Version object."""

    if match := re.match(r"^(\d+\.\d+\.\d+)-daily$", version):
        return VersionWithReleaseDate(
            base_version=BaseVersion.from_str(match.group(1)),
            release_date=datetime.today().date(),
        )

    if match := re.match(r"^(\d+\.\d)+$", version):
        return PartialVersion.from_str(match.group(1))

    if match := re.match(r"^(\d+\.\d+\.\d+)$", version):
        return BaseVersion.from_str(match.group(1))

    if match := re.match(r"^(\d+\.\d+(?:\.\d+)?)(p|b)(\d+)$", version):
        return VersionWithPatch(
            base_version=BaseVersion.from_str(match.group(1)),
            patch_type="p" if match.group(2) == "p" else "b",
            patch=int(match.group(3)),
        )

    if match := re.match(r"^git:(.+?):(.+?)$", version):
        return GitVersion(
            branch=match.group(1),
            commit_hash=match.group(2),
        )

    if match := re.match(r"^(\d+\.\d+\.\d+)-(\d+[.-]\d+[.-]\d+)$", version):
        return VersionWithReleaseDate(
            base_version=BaseVersion.from_str(match.group(1)),
            release_date=datetime.strptime(match.group(2).replace(".", "-"), "%Y-%m-%d").date(),
        )

    raise argparse.ArgumentTypeError(
        f"{version!r} doesn't match expected format '2.2.0p23|2.2.0-YYYY-MM-DD|2.2.0-YYYY.MM.DD|"
        "2.2|2.2.0-daily|git:<branch>:<commit_hash>'"
    )


class FileServer:
    """Represents a file server to download packages from."""

    def __init__(
        self,
        user: str,
        password: str,
    ):
        self.user = user
        self.password = password
        self._session = requests.Session()
        self._session.auth = (user, password)
        self._timeout = 120

    def _get(self, url: str, **kwargs: Any) -> requests.Response:
        try:
            response = self._session.get(url, timeout=self._timeout, **kwargs)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"ERROR: {e}") from e

        return response

    @log(max_level=logging.DEBUG)
    def download_hash(self, download_url: str) -> str:
        """Download the hash file for a given file."""
        response = self._get(f"{download_url}.hash")

        hash_data = response.text.strip().split()

        if not hash_data:
            raise ValueError("Empty or invalid hash file.")

        return hash_data[0]

    def _calculate_file_hash(self, file_path: Path, hash_type: str = "sha256") -> str:
        """
        Calculate the hash of a file.

        :param file_path: Path to the file.
        :param hash_type: Hash algorithm (e.g., 'sha256', 'md5', 'sha1').
        :return: Hexadecimal hash of the file.
        """
        try:
            with open(file_path, "rb") as f:
                digest = hashlib.file_digest(f, hash_type)
            return digest.hexdigest()
        except FileNotFoundError as e:
            raise RuntimeError(f"ERROR: File not found: {file_path}") from e

    @log()
    def verify_hash(self, download_url: str, file_path: Path) -> bool:
        """
        Verify the hash of a file.
        :param download_url: The URL of the hash file.
        :param file_path: Path to the file.
        :return: True if the hash matches, False otherwise.
        """
        file_hash = self.download_hash(download_url)
        calculated_hash = self._calculate_file_hash(file_path)

        return file_hash == calculated_hash

    @log()
    def download_package(
        self,
        url: str,
        download_path: Path,
    ) -> None:
        """
        Downloads a package from the file server.

        :param url: The URL of the package.
        :param download_path: The local path where the package will be saved.
        """

        start = time.monotonic()
        response = self._get(
            url,
            stream=True,
        )

        file_size = int(response.headers["Content-Length"])
        with open(download_path, "wb") as file:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                file.write(chunk)
                downloaded += len(chunk)
                progress = (downloaded / file_size) * 100
                download_rate = downloaded / 1024 / 1024 / (time.monotonic() - start)
                logger.progress(f"Downloading... {progress:.2f}% ({download_rate:.2f} MB/s)")

    def _query_available_versions(self, url: str) -> Sequence[VersionWithReleaseDate]:
        response = self._get(url)
        vs_parser = VersionParser()
        vs_parser.feed(response.text)
        return vs_parser.versions

    @log(max_level=logging.DEBUG)
    def list_versions_with_date(
        self, url: str, base_version: BaseVersion
    ) -> list[VersionWithReleaseDate]:
        return [vs for vs in self._query_available_versions(url) if vs.base_version == base_version]

    @log()
    def query_latest_base_version(self, urls: list[str]) -> BaseVersion:
        # if we have no version *at all*, this raises.
        return max(
            (v.base_version for url in urls for v in self._query_available_versions(url)),
        )

    @log()
    def url_exists(self, url: str) -> bool:
        response = self._session.head(
            url,
            timeout=self._timeout,
        )
        return response.status_code == 200


class VersionParser(HTMLParser):
    """
    This class is used to parse the versions from the Checkmk download page with re.Pattern.
    """

    def __init__(self) -> None:
        super().__init__()
        self._versions: list[VersionWithReleaseDate] = []
        self._pattern = re.compile(r"^(\d+\.\d+\.\d+)-(\d+.\d+.\d+)")

    @property
    def versions(self) -> Sequence[VersionWithReleaseDate]:
        return self._versions

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)

        if tag == "a" and (href := attrs_dict.get("href")) and (match := self._pattern.match(href)):
            self._versions.append(
                VersionWithReleaseDate(
                    base_version=BaseVersion.from_str(match.group(1)),
                    release_date=datetime.strptime(match.group(2), "%Y.%m.%d").date(),
                )
            )


@log()
def validate_jenkins_jobs_ini() -> bool:
    """
    Validate the jenkins_jobs.ini file exists or not.
    """

    if not CONFIG_PATH.exists():
        this_user_name = run_command(["git", "config", "user.email"]).stdout.strip().split("@")[0]
        config_content = f"""
In order to interact with Jenkins you need to have a file at
"~/.config/jenkins_jobs/jenkins_jobs.ini" containing the following content

# start of file
[jenkins]
user={this_user_name}
# Get the APIKEY from the CI web UI, click top right Profile -> Security -> Add new Token
# https://ci.lan.tribe29.com/user/{this_user_name}/security
password=API_KEY_NOT_YOUR_PASSWORD
url=https://ci.lan.tribe29.com
query_plugins_info=False
# end of file
"""
        logger.error(
            config_content,
        )
        return False
    return True


@dataclass
class ArtifactsResult:
    artifacts: list[str]
    result: str


@log()
def build_install_git_version(
    branch: str, commit_hash: str, edition: Edition, distro_id: str
) -> Path:
    """
    Build and install a version from a specific branch and commit hash.

    :param branch: The branch to build the version from.
    :param commit_hash: The commit hash to build the version from.
    :param edition: The edition of the version.
    :param distro_id: The distro ID to build the version for.
    :return: The path to the built package.
    """

    if not validate_jenkins_jobs_ini():
        raise RuntimeError("ERROR: Jenkins jobs ini file is not found")

    if not shutil.which("ci-artifacts"):
        raise RuntimeError(
            "'ci-artifacts' command not found."
            "To have 'ci-artifacts' available, run 'pip install checkmk-dev-tools' and try again"
        )

    result = run_command(
        [
            "ci-artifacts",
            "fetch",
            f"checkmk/{branch}/builders/build-cmk-distro-package",
            "--out-dir",
            "/tmp/",
            "--no-remove-others",
            f"--params=DISTRO=ubuntu-{distro_id},EDITION={edition.name.lower()},CUSTOM_GIT_REF={commit_hash}",
        ],
    )
    typed_result = ArtifactsResult(**json.loads(result.stdout))
    if typed_result.result == "FAILURE":
        raise RuntimeError("ERROR: Failed to build the version.")

    filtered_artifacts = [
        artifact
        for artifact in typed_result.artifacts
        if "check-mk" in artifact and artifact.endswith(".deb")
    ]

    if not filtered_artifacts:
        raise RuntimeError("ERROR: No artifacts found for the version.")

    return Path("/tmp", filtered_artifacts[0])


@log()
def find_last_release(
    file_server: FileServer,
    base_version: BaseVersion,
    edition: Edition,
    distro_codename: str,
) -> CMKPackage:
    """
    Find the last release date for a version.
    """
    url_version_date = [
        (CMK_DOWNLOAD_URL, v_date)
        for v_date in file_server.list_versions_with_date(CMK_DOWNLOAD_URL, base_version)
    ] + [
        (TSBUILD_URL, v_date)
        for v_date in file_server.list_versions_with_date(TSBUILD_URL, base_version)
    ]

    url_version_date.sort(key=lambda p: p[1].release_date, reverse=True)

    for url, version_date in url_version_date:
        pkg = CMKPackage(
            version=version_date,
            edition=edition,
            distro_codename=distro_codename,
        )
        if file_server.url_exists(build_download_url(url, pkg)):
            return pkg

    raise RuntimeError(f"ERROR: No release found for the version {base_version}")


@log(max_level=logging.DEBUG)
def find_sitenames_by_version(version: str) -> list[str]:
    """
    Get the list of sitenames that are running by a specific version
    """
    site_names: list[str] = []
    try:
        for path in Path("/omd/sites").glob("*"):
            path = path / "version"
            if path.is_symlink():
                target = path.readlink()  # Read the symlink target
                site_version = target.name  # Extract the version from the target path
                site_name = path.parent.name
                if site_version == version:
                    site_names.append(site_name)
        return site_names
    except OSError as e:
        raise RuntimeError(f"ERROR: {e.strerror}") from e


def apply_acls_to_version(version: str) -> None:
    """
    Apply ACLs to omd version.
    """
    version_path = INSTALLATION_PATH / version
    user = getpass.getuser()

    if not version_path.exists():
        raise RuntimeError(f"ERROR: Version {version_path.name} does not exist")
    run_command(
        [
            "sudo",
            "setfacl",
            "--recursive",
            "-m",
            f"user:{user}:rwX",
            str(version_path),
        ],
    )


def get_default_version() -> str:
    return run_command(["sudo", "omd", "version", "-b"]).stdout.strip()


@log(max_level=logging.DEBUG)
def set_default_version(version: str) -> None:
    """
    Set the default version to the specified version.
    """
    if version == get_default_version():
        return
    run_command(
        ["sudo", "omd", "setversion", version],
    )


@log()
def ensure_sudo() -> None:
    """It increases the sudo timeout and refreshes it."""
    run_command(["sudo", "-v"])


class ArgFormatter(argparse.RawTextHelpFormatter):
    pass


class DevInstallArgs(argparse.Namespace):
    build: Version
    edition: Edition
    force: bool
    verbose: int
    quiet: int
    download_only: bool


def create_parser() -> argparse.ArgumentParser:
    assert __doc__ is not None, "__doc__ must be a non-None string"
    prog, descr = __doc__.split("\n", 1)

    parser = argparse.ArgumentParser(
        prog=prog,
        description=descr,
        formatter_class=ArgFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def setup_parser(parser: argparse.ArgumentParser) -> None:
    """Setup the argument parser for the script."""

    parser.add_argument(
        "build",
        metavar="version",
        type=parse_version,
        nargs="?",
        help=f"""specify the version in one of the following formats:

  {colorize("2.4.0-daily", "green")}: install today's daily version
  {colorize("2.4", "green")}: install the latest available daily build
  {colorize("2.4.0-2025-01-01", "green")}: install specific daily version
  {colorize("2.4.0p23", "green")}: install released patch version
  {colorize("git:master:39f57c98f92", "green")}: Build and install from a specific
    branch and commit

Per default it will try to install the daily version of the
latest branch that can be found.
""",
    )

    parser.add_argument(
        "-e",
        "--edition",
        type=Edition,
        default=Edition.ENTERPRISE,
        choices=Edition,
        help="specify the edition of the version to install (default: %(default)s).",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force re-downloading and installing the version.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase output verbosity",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="count",
        default=0,
        help="suppress stderr output.'-q': suppress info, '-qq': suppress warnings.",
    )
    parser.add_argument(
        "-d",
        "--download-only",
        action="store_true",
        help="download only (do not install)",
    )


@log(max_level=logging.DEBUG)
def validate_installation(cmk_pkg: CMKPackage, force: bool, download_only: bool) -> bool:
    """
    Validate if the installation should go through.
    """
    already_installed = (INSTALLATION_PATH / Path(cmk_pkg.omd_version)).exists()

    if already_installed and not (force or download_only):
        logger.warning(
            "Version %s already installed.", INSTALLATION_PATH / Path(cmk_pkg.omd_version)
        )
        logger.warning("Use --force to re-download and re-install.")

        return False

    if (
        already_installed
        and (existed_sitenames := find_sitenames_by_version(cmk_pkg.omd_version))
        and not download_only
    ):
        nl = "\n"
        raise RuntimeError(
            f"Found sites existed with the version {cmk_pkg.omd_version}: {existed_sitenames}\n"
            "Please remove the site, before reinstalling using:\n"
            f"""{
                nl.join(
                    [
                        f"sudo omd -f rm --kill --apache-reload {sitename}"
                        for sitename in existed_sitenames
                    ]
                )
            }"""
        )

    return True


def download_and_install_cmk_pkg(
    file_server: FileServer,
    urls: list[str],
    cmk_pkg: CMKPackage,
    force: bool,
    download_only: bool,
) -> CMKPackage:
    """
    Download and install a Checkmk package.
    """
    if not validate_installation(cmk_pkg, force, download_only):
        set_default_version(cmk_pkg.omd_version)
        return cmk_pkg

    download_path = DOWNLOAD_DIR / cmk_pkg.package_name
    valid_url = None
    for url in urls:
        logger.debug(f"Checking URL: {url}")
        pkg_url = build_download_url(url, cmk_pkg)

        if not file_server.url_exists(pkg_url):
            logger.warning(f"Version {cmk_pkg} not found in the download server {url}")
        else:
            valid_url = pkg_url

    if valid_url is None:
        raise RuntimeError("Download URL not found.")
    file_server.download_package(
        url=valid_url,
        download_path=download_path,
    )
    if not (file_server.verify_hash(valid_url, download_path)):
        raise RuntimeError("ERROR: Hash verification failed.")
    if not download_only:
        remove_package(cmk_pkg.package_raw_name, INSTALLATION_PATH / Path(cmk_pkg.omd_version))
        install_package(download_path)
    return cmk_pkg


@log()
def is_on_vpn() -> bool:
    hostname = TSBUILD_URL.replace("https://", "").split("/")[0]
    resolved_ip = socket.gethostbyname(hostname)
    in_vpn_or_office = resolved_ip != "45.133.11.62"
    if not in_vpn_or_office:
        return False
    # make sure we are not in the office, but not connected to vpn
    result = run_command(
        ["ping", "-q", "-c", "1", "-W", "1", "tstbuilds-artifacts.lan.tribe29.com"],
        raise_runtime_error=False,
    )
    # we can not ping tsbuilds in the office without vpn, although it resolves to the correct ip
    return result.returncode == 0


@log(max_level=logging.DEBUG)
def core_logic(
    version: Version | None, edition: Edition, force: bool, download_only: bool
) -> tuple[str, Path]:
    """
    Download and Install a Checkmk version.

    :param version: The version to install.
    :param edition: The edition of the version.
    :param force: Re-download and re-install the version.
    :param download: Download only (no install).
    :return: The installed version and the package path.
    """
    if not download_only:
        ensure_sudo()
    if is_on_vpn() is False:
        logger.warning("You are not on the VPN, tstbuilds might not be reachable.")
        download_urls = [CMK_DOWNLOAD_URL]
    else:
        download_urls = [CMK_DOWNLOAD_URL, TSBUILD_URL]
    user, password = get_user_pass()
    file_server = FileServer(user=user, password=password)
    distro = get_distro_version_info()

    match version:
        case GitVersion(branch=branch, commit_hash=commit_hash):
            pkg_path = build_install_git_version(branch, commit_hash, edition, distro.version_id)
            install_package(pkg_path)
            # default version will point to the latest installed version
            # we don't have to figure out which git version we just installed
            installed_version = get_default_version()

        case PartialVersion():
            cmk_pkg = find_last_release(file_server, version, edition, distro.version_codename)
            cmk_pkg = download_and_install_cmk_pkg(
                file_server=file_server,
                urls=download_urls,
                cmk_pkg=cmk_pkg,
                force=force,
                download_only=download_only,
            )
            pkg_path = DOWNLOAD_DIR / cmk_pkg.package_name
            installed_version = cmk_pkg.omd_version
        case _:
            if version is None:
                version = VersionWithReleaseDate(
                    base_version=file_server.query_latest_base_version(download_urls),
                    release_date=datetime.today().date(),
                )
            cmk_pkg = CMKPackage(
                version=version,
                edition=edition,
                distro_codename=distro.version_codename,
            )
            cmk_pkg = download_and_install_cmk_pkg(
                file_server=file_server,
                urls=download_urls,
                cmk_pkg=cmk_pkg,
                force=force,
                download_only=download_only,
            )
            pkg_path = DOWNLOAD_DIR / cmk_pkg.package_name
            installed_version = cmk_pkg.omd_version

    if not download_only:
        apply_acls_to_version(installed_version)

    return installed_version, pkg_path


def execute(args: argparse.Namespace) -> int:
    logger.setLevel(max(logging.INFO - ((args.verbose - args.quiet) * 10), logging.DEBUG))

    if args.verbose - args.quiet > 3:
        # disable the custom logging, otherwise we see all messages twice
        logger.removeHandler(logger.handlers[0])
        logging.basicConfig(level=logging.DEBUG)
        logger_urllib = logging.getLogger("requests.packages.urllib3")
        logger_urllib.setLevel(logging.DEBUG)
        logger_urllib.propagate = True

    if args.verbose - args.quiet > 4:
        http.client.HTTPConnection.debuglevel = 1

    try:
        installed_version, pkg_path = core_logic(
            args.build, args.edition, args.force, args.download_only
        )
    except RuntimeError as e:
        logger.error(e)
        return 1

    print(installed_version)
    if args.download_only:
        print(pkg_path)
    return 0


def main(sys_argv: list[str] | None = None) -> int:
    parser = create_parser()
    setup_parser(parser)

    args = parser.parse_args(sys_argv or sys.argv[1:], namespace=DevInstallArgs())
    return execute(args)

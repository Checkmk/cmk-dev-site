#!/usr/bin/env -S python3 -u
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
import functools
import getpass
import hashlib
import json
import logging
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Literal, Optional, ParamSpec, TypeVar

import requests

CREDENTIALS_FILE = Path("~/.cmk-credentials").expanduser()
PROGRESS_LEVEL = 25  # Between  INFO (20) and WARNING (30)
CONFIG_PATH = Path("~/.config/jenkins_jobs/jenkins_jobs.ini").expanduser()
INSTALLATION_PATH = Path("/omd/versions")
TSBUILD_URL = "https://tstbuilds-artifacts.lan.tribe29.com"
CMK_DOWNLOAD_URL = "https://download.checkmk.com/checkmk"
# Custom log level for progress updates
logging.addLevelName(PROGRESS_LEVEL, "INFO")
logger = logging.getLogger(__name__)

T = TypeVar("T")  # Type variable for a generic type
P = ParamSpec("P")  # Type variable for a function's parameters


def log(
    info_message: Optional[str] = None,
    error_message: Optional[str] = None,
    message_info: Optional[Callable[P, str]] = None,
    prefix: Optional[Callable[P, str]] = None,
    max_level: int = logging.INFO,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for logging function calls, handling errors with optional warnings

    :param info_message: The message to log before the function call.
    :param error_message: The message to log if the function raises an exception.
    :param message_info: A function to generate a custom info message based on the function's arguments.
    :param prefix: A function to generate a custom prefix for the info message based on the function's arguments.
    :param max_level: maximum logging level to use for logging message.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            formated_func_name = func.__name__.replace("_", " ").capitalize()
            if message_info:
                msg = message_info(*args, **kwargs)
            else:
                msg = info_message or f"{formated_func_name}..."

            if prefix:
                msg = prefix(*args, **kwargs) + msg

            # Log function call details
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Calling %s with args: %s, kwargs: %s",
                    colorize(func.__name__, "cyan"),
                    args,
                    kwargs,
                )
            else:
                if max_level >= logging.INFO:
                    logger.log(PROGRESS_LEVEL, msg)

            try:
                result = func(*args, **kwargs)

            except Exception:  # pylint: disable=broad-except
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("%s Trace:", func.__name__, exc_info=True)
                else:
                    logger.info("%s%s", msg, colorize("Failed", "red"))
                if error_message:
                    logger.error(error_message)

                # re-raise the exception
                raise
            else:
                # Log function result details
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "%s returned: %s", colorize(func.__name__, "cyan"), result
                    )

                else:
                    if max_level >= logging.INFO:
                        msg = (
                            f"{msg}{colorize('OK', 'green')}"
                            if result is None
                            else f"{msg}-> {colorize(str(result), 'green')}"
                        )
                        logger.info("%s", msg)

                return result

        return wrapper

    return decorator


@functools.total_ordering
class BaseVersion:
    def __init__(self, major: int, minor: int, patch: int = 0):
        self.major = major
        self.minor = minor
        self.patch = patch

    @classmethod
    def from_str(cls, version_str: str) -> "BaseVersion":
        """Create a Version object from a string.
        This method expects the version string to be in the format 'd.d[.d]'.
        """
        match version_str.split("."):
            case (major_str, minor_str):
                return cls(major=int(major_str), minor=int(minor_str))
            case (major_str, minor_str, patch_str):
                return cls(
                    major=int(major_str), minor=int(minor_str), patch=int(patch_str)
                )
        raise ValueError("Version must be in 'd.d[.d]' format")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __eq__(self, other):
        if isinstance(other, BaseVersion):
            return (self.major, self.minor, self.patch) == (
                other.major,
                other.minor,
                other.patch,
            )
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, BaseVersion):
            return (self.major, self.minor, self.patch) < (
                other.major,
                other.minor,
                other.patch,
            )
        return NotImplemented


class PartialVersion(BaseVersion):
    """Represents a version that release date is not known."""

    pass


class VersionWithPatch:
    def __init__(
        self, base_version: BaseVersion, patch_type: Literal["p", "b"], patch: int
    ):
        self.base_version = base_version
        self.patch_type = patch_type
        self.patch = patch

    def __str__(self) -> str:
        return f"{self.base_version}{self.patch_type}{self.patch}"

    def iso_format(self) -> str:
        return f"{self.base_version}{self.patch_type}{self.patch}"


class VersionWithReleaseDate:
    def __init__(self, base_version: BaseVersion, release_date: date):
        self.base_version = base_version
        self.release_date = release_date

    def __str__(self) -> str:
        return f"{self.base_version}-{self.release_date.strftime('%Y.%m.%d')}"

    def __repr__(self) -> str:
        return self.__str__()

    def iso_format(self) -> str:
        return f"{self.base_version}-{self.release_date.isoformat()}"


class GitVersion:
    def __init__(self, branch: str, commit_hash: str):
        self.branch = branch
        self.commit_hash = commit_hash

    def __str__(self) -> str:
        return f"git:{self.branch}:{self.commit_hash}"


type Version = (
    BaseVersion
    | VersionWithPatch
    | VersionWithReleaseDate
    | PartialVersion
    | GitVersion
)


class Edition(StrEnum):
    RAW = "cre"
    ENTERPRISE = "cee"
    MANAGED = "cme"
    CLOUD = "cce"
    SAAS = "cse"


class CMKPackage:
    """Represents a Checkmk package."""

    def __init__(
        self,
        version: VersionWithPatch | VersionWithReleaseDate | BaseVersion,
        edition: Edition,
        distro_codename: str,
        base_url: str = CMK_DOWNLOAD_URL,
        arch: str = "amd64",
    ):
        self.version = version
        self.edition = edition
        self.distro_codename = distro_codename
        self.base_url = base_url
        self.arch = arch

    @property
    def omd_version(self) -> str:
        """Get the OMD version string."""
        return f"{self.version}.{self.edition.value}"

    @property
    def package_raw_name(self) -> str:
        """Get the package name."""
        return f"check-mk-{self.edition.name.lower()}-{self.version}"

    @property
    def package_name(self) -> str:
        """Get the package name."""
        return f"{self.package_raw_name}_0.{self.distro_codename}_{self.arch}.deb"

    @property
    def download_path(self) -> Path:
        """Get the download path for the package."""
        return Path("/tmp", self.package_name)

    @property
    def download_url(self) -> str:
        """Get the absolute download URL for the package."""
        return f"{self.base_url}/{self.version}/{self.package_name}"

    @property
    def installed_path(self) -> Path:
        """Get the path where the package is installed."""
        return INSTALLATION_PATH / Path(self.omd_version)

    def __str__(self) -> str:
        return f"{self.version}.{self.edition.value}"

    def __repr__(self) -> str:
        return self.__str__()


@log()
def remove_package(pkg_name: str, installed_path: Path) -> None:
    """
    Remove a package using apt.
    """
    if not installed_path.exists():
        return

    try:
        result = subprocess.run(
            [
                "sudo",
                "apt-get",
                "purge",
                "-y",
                pkg_name,
            ],
            check=True,  # Raises CalledProcessError if the command fails
            stdout=subprocess.PIPE,  # Captures standard output
            stderr=subprocess.PIPE,  # Captures standard error
            text=True,  # Decodes output as text (str)
        )
        logger.debug(result.stdout)
        # making sure the path is relative to /omd/versions/
        if not installed_path.is_relative_to(INSTALLATION_PATH):
            raise RuntimeError(
                f"ERROR: Removing package failed: {installed_path} is not a valid path"
            )
        subprocess.run(
            [
                "sudo",
                "rm",
                "-rf",
                str(installed_path),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to remove package: {e.stderr}")


@log()
def install_packet(pkg_path: Path) -> None:
    """
    Install a package using apt from the provided file path.
    """
    try:
        # Run the apt install command with sudo and capture output
        result = subprocess.run(
            [
                "sudo",
                "apt-get",
                "install",
                "-y",
                str(pkg_path),
            ],
            check=True,  # Raises CalledProcessError if the command fails
            stdout=subprocess.PIPE,  # Captures standard output
            stderr=subprocess.PIPE,  # Captures standard error
            text=True,  # Decodes output as text (str)
        )
        logger.debug(result.stdout)

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to install package: {e.stderr}")


def colorize(text: str, color: str) -> str:
    """Colorize text with ANSI escape codes."""
    colors = {
        "blue": "\033[34m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "red": "\033[31m",
        "magenta": "\033[35;1m",
        "cyan": "\033[36m",
    }
    rest = "\033[0m"
    if color_code := colors.get(color):
        return f"{color_code}{text}{rest}"

    return text


class ColoredFormatter(logging.Formatter):
    """Custom log formatter that colorizes log messages based on their level."""

    # Define ANSI escape codes for colors
    COLORS = {
        logging.DEBUG: "blue",  # Blue
        logging.INFO: "green",  # Green
        logging.WARNING: "yellow",  # Yellow
        logging.ERROR: "red",  # Red
        logging.CRITICAL: "magenta",  # Bright Magenta
        PROGRESS_LEVEL: "cyan",  # Cyan
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")

        # Colorize the levelname using termcolor
        record.levelname = colorize(record.levelname, color)

        # Call the parent format method to handle the message formatting
        return super().format(record)


class InlineStreamHandler(logging.StreamHandler):
    """Custom StreamHandler to support inline logging for progress updates."""

    def __init__(self):
        super().__init__(sys.stderr)
        self.current_inline_message = False

    def emit(self, record: logging.LogRecord) -> None:
        # Format the message
        msg = self.format(record)
        if record.levelno == PROGRESS_LEVEL:
            # Overwrite the same line for progress
            print(f"\r\033[K{msg}", end="", flush=True, file=sys.stderr)
            self.current_inline_message = True
        else:
            # Clear inline message if switching to a regular log
            if self.current_inline_message:
                print(f"\r\033[K{msg}", flush=True, file=sys.stderr)
                self.current_inline_message = False
            else:
                print(msg, flush=True, file=sys.stderr)


def setup_logging(verbose: int) -> None:
    """Configure the logging system."""

    console_handler = InlineStreamHandler()

    log_level = max(
        logging.INFO - (verbose * 10), logging.DEBUG
    )  # Map verbosity to log levels
    logger.setLevel(log_level)

    # Use the ColoredFormatter
    formatter = ColoredFormatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def get_user_pass() -> tuple[str, str]:
    """Get the user and password from the credentials file"""

    try:
        user, password = (
            CREDENTIALS_FILE.read_text(encoding="utf-8").strip().split(":", 1)
        )
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

    if match := re.match(r"^(\d+\.\d+\.\d+)-(\d+-\d+-\d+)$", version):
        return VersionWithReleaseDate(
            base_version=BaseVersion.from_str(match.group(1)),
            release_date=datetime.strptime(match.group(2), "%Y-%m-%d").date(),
        )

    raise argparse.ArgumentTypeError(
        f"{version!r} doesn't match expected format '2.2.0p23|2.2.0-YYYY-MM-DD|2.2|2.2.0-daily|git:<branch>:<commit_hash>'"
    )


class FileServer:
    """Represents a file server to download packets from."""

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
    def download_packet(
        self,
        url: str,
        download_path: Path,
    ) -> None:
        """
        Downloads a packet from the file server.

        :param url: The URL of the packet.
        :param download_path: The local path where the packet will be saved.
        """

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
                logger.log(PROGRESS_LEVEL, f"Downloading... {progress:.2f}%")

    def _query_available_versions(self, url: str) -> Sequence[VersionWithReleaseDate]:
        response = self._get(url)
        vs_parser = VersionParser()
        vs_parser.feed(response.text)
        return vs_parser.versions

    @log(max_level=logging.DEBUG)
    def list_versions_with_date(
        self, url: str, base_version: BaseVersion
    ) -> list[VersionWithReleaseDate]:
        return [
            vs
            for vs in self._query_available_versions(url)
            if vs.base_version == base_version
        ]

    @log()
    def query_latest_base_version(self, *urls: str) -> BaseVersion:
        # if we have no version *at all*, this raises.
        return max(
            (
                v.base_version
                for url in urls
                for v in self._query_available_versions(url)
            ),
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

        if (
            tag == "a"
            and (href := attrs_dict.get("href"))
            and (match := self._pattern.match(href))
        ):
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
        this_user_name = (
            subprocess.check_output(["git", "config", "user.email"])
            .decode()
            .strip()
            .split("@")[0]
        )
        config_content = f"""
In order to interact with Jenkins you need to have a file at "~/.config/jenkins_jobs/jenkins_jobs.ini" containing
the following content

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
    branch: str, commit_hash: str, edition: Edition, distro_id
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

    result = subprocess.run(
        [
            "ci-artifacts",
            "fetch",
            f"checkmk/{branch}/builders/build-cmk-distro-package",
            "--out-dir",
            "/tmp/",
            "--no-remove-others",
            f"--params=DISTRO=ubuntu-{distro_id},EDITION={edition.name.lower()},CUSTOM_GIT_REF={commit_hash}",
        ],
        check=True,
        stdout=subprocess.PIPE,
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
        for v_date in file_server.list_versions_with_date(
            CMK_DOWNLOAD_URL, base_version
        )
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
            base_url=url,
        )
        if file_server.url_exists(pkg.download_url):
            return pkg

    raise RuntimeError(f"ERROR: No release found for the version {base_version}")


@log(max_level=logging.DEBUG)
def find_sitenames_by_version(version: str) -> list[str]:
    """
    Get the list of sitenames that are running by a specific version
    """
    site_names = []
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

    try:
        if not version_path.exists():
            raise RuntimeError(f"ERROR: Version {version_path.name} does not exist")
        subprocess.run(
            [
                "sudo",
                "setfacl",
                "--recursive",
                "-m",
                f"user:{user}:rwX",
                version_path,
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ERROR: {e.stderr}") from e


def get_default_version() -> str:
    return subprocess.check_output(("sudo", "omd", "version", "-b"), text=True).strip()


@log(max_level=logging.DEBUG)
def set_default_version(version: str) -> None:
    """
    Set the default version to the specified version.
    """
    if version == get_default_version():
        return
    try:
        subprocess.run(
            ["sudo", "omd", "setversion", version],
            check=True,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr) from e


@log()
def ensure_sudo() -> None:
    """It increases the sudo timeout and refreshes it."""
    subprocess.run(["sudo", "-v"], check=True)


class ArgFormatter(argparse.RawTextHelpFormatter):
    pass


class DevInstallArgs(argparse.Namespace):
    build: Version
    edition: Edition
    force: bool
    verbose: int
    quiet: int
    download_only: bool


def setup_parser() -> argparse.ArgumentParser:
    """Setup the argument parser for the script."""

    assert __doc__ is not None, "__doc__ must be a non-None string"
    prog, descr = __doc__.split("\n", 1)

    parser = argparse.ArgumentParser(
        prog=prog,
        description=descr,
        formatter_class=ArgFormatter,
    )
    parser.add_argument(
        "build",
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

    return parser


@log(max_level=logging.DEBUG)
def validate_installation(
    cmk_pkg: CMKPackage, force: bool, download_only: bool
) -> bool:
    """
    Validate if the instllation should go through.
    """
    already_installed = cmk_pkg.installed_path.exists()

    if already_installed and not (force or download_only):
        logger.warning("Version %s already installed.", cmk_pkg.installed_path)
        logger.warning("Use --force to re-download and re-install.")

        return False

    if (
        already_installed
        and (existed_sitenames := find_sitenames_by_version(cmk_pkg.omd_version))
        and not download_only
    ):
        raise RuntimeError(
            f"Found sites existed with the version {cmk_pkg.omd_version}: {existed_sitenames}\n"
            "Please remove the site, before reinstalling using:\n"
            f"""{
                '\n'.join(
                    [
                        f'sudo omd -f rm --kill --apache-reload {sitename}'
                        for sitename in existed_sitenames
                    ]
                )
            }"""
        )

    return True


def download_and_install_cmk_pkg(
    file_server: FileServer, cmk_pkg: CMKPackage, force: bool, download_only: bool
) -> CMKPackage:
    """
    Download and install a Checkmk package.
    """
    if not validate_installation(cmk_pkg, force, download_only):
        set_default_version(cmk_pkg.omd_version)
        return cmk_pkg
    file_server.download_packet(
        url=cmk_pkg.download_url,
        download_path=cmk_pkg.download_path,
    )
    if not (file_server.verify_hash(cmk_pkg.download_url, cmk_pkg.download_path)):
        raise RuntimeError("ERROR: Hash verification failed.")
    if not download_only:
        remove_package(cmk_pkg.package_raw_name, cmk_pkg.installed_path)
        install_packet(cmk_pkg.download_path)
    return cmk_pkg


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
    user, password = get_user_pass()
    file_server = FileServer(user=user, password=password)
    distro = get_distro_version_info()

    match version:
        case GitVersion(branch=branch, commit_hash=commit_hash):
            pkg_path = build_install_git_version(
                branch, commit_hash, edition, distro.version_id
            )
            install_packet(pkg_path)
            # default version will point to the latest installed version
            # we don't have to figure out which git version we just installed
            installed_version = get_default_version()

        case PartialVersion():
            cmk_pkg = find_last_release(
                file_server, version, edition, distro.version_codename
            )
            cmk_pkg = download_and_install_cmk_pkg(
                file_server, cmk_pkg, force, download_only
            )
            pkg_path = cmk_pkg.download_path
            installed_version = cmk_pkg.omd_version
        case _:
            if version is None:
                version = VersionWithReleaseDate(
                    base_version=file_server.query_latest_base_version(
                        CMK_DOWNLOAD_URL, TSBUILD_URL
                    ),
                    release_date=datetime.today().date(),
                )
            cmk_pkg = CMKPackage(
                version=version,
                edition=edition,
                distro_codename=distro.version_codename,
            )
            if not file_server.url_exists(cmk_pkg.download_url):
                logger.warning(
                    f"Version {version} not found in the download server. Trying tstbuilds server."
                )
                cmk_pkg.base_url = TSBUILD_URL
            cmk_pkg = download_and_install_cmk_pkg(
                file_server, cmk_pkg, force, download_only
            )
            pkg_path = cmk_pkg.download_path
            installed_version = cmk_pkg.omd_version

    if not download_only:
        apply_acls_to_version(installed_version)

    return installed_version, pkg_path


def main() -> int:
    parser = setup_parser()
    args = parser.parse_args(namespace=DevInstallArgs)
    setup_logging(args.verbose - args.quiet)

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


if __name__ == "__main__":
    sys.exit(main())

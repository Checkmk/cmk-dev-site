import logging
import socket
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .log import colorize


def run_command(
    args: Sequence[str],
    check: bool = True,
    error_message: str | None = None,
    raise_runtime_error: bool = True,
    text: bool = True,
    logger: logging.Logger | None = logging.getLogger(__name__),
    silent: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    result = subprocess.run(args=args, capture_output=True, text=text, **kwargs)
    msg = f"Running command {colorize(' '.join(args), 'blue')}:"
    if not silent and result.stdout:
        msg = msg + "\nSTDOUT:\n" + colorize(result.stdout.strip(), "green")
    if not silent and result.stderr:
        msg = msg + "\nSTDERR:\n" + colorize(result.stderr.strip(), "red")
    if logger:
        logger.debug(msg)
    if check and result.returncode != 0:
        if raise_runtime_error:
            error_msg = (error_message + "\n") if error_message else ""
            error_msg += (
                f"ERROR: Command failed: {colorize(' '.join(args), 'red')}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
            raise RuntimeError(error_msg)
        else:
            if logger and error_message:
                logger.warning(error_message)

    return result


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def create_root_owned_file(file: Path) -> None:
    run_command(["sudo", "mkdir", "-p", file.parent.absolute().as_posix()])
    run_command(["sudo", "touch", file.absolute().as_posix()])
    run_command(["sudo", "chmod", "0666", file.absolute().as_posix()])

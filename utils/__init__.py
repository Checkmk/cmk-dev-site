import logging
import subprocess
from collections.abc import Sequence
from typing import (
    Any,
)

from .log import colorize


def run_command(
    args: Sequence[str],
    check: bool = True,
    error_message: str | None = None,
    raise_runtime_error: bool = True,
    text: bool = True,
    silent: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    logger = logging.getLogger(__name__)
    result = subprocess.run(args=args, capture_output=True, text=text, **kwargs)
    msg = f"Running command: \n{colorize(' '.join(args), 'blue')}"
    if not silent and result.stdout:
        msg = msg + "\nSTDOUT:\n " + colorize(result.stdout.strip(), "green")
    if not silent and result.stderr:
        msg = msg + "\nSTDERR:\n " + colorize(result.stderr.strip(), "red")
    logger.debug(msg)
    if check and result.returncode != 0:
        error_msg = (error_message + "\n") if error_message else ""
        error_msg += (
            f"ERROR: Command failed: {colorize(' '.join(args), 'red')}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        if raise_runtime_error:
            raise RuntimeError(error_msg)
        else:
            logger.warning(error_msg)

    return result

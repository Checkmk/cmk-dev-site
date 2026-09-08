import signal
import sys
from collections.abc import Generator
from contextlib import contextmanager
from types import FrameType


@contextmanager
def clean_cli_exit() -> Generator[None, None, None]:
    """Context manager for clean keyboard interrupt and signal handling."""

    def signal_handler(signum: int, frame: FrameType | None) -> None:
        print(f"\n\nReceived signal {signum}.", file=sys.stderr)
        sys.exit(128 + signum)

    for sig in [signal.SIGTERM, signal.SIGHUP]:
        signal.signal(sig, signal_handler)

    try:
        yield
    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl-C).", file=sys.stderr)
        sys.exit(130)


def resolve_argv(sys_argv: list[str] | None, fallback: list[str]) -> list[str]:
    """Return the arguments to parse: `None` means fall back to `fallback`,
    while an empty list means no arguments at all."""
    return fallback if sys_argv is None else sys_argv

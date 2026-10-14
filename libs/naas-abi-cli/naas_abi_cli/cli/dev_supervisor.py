"""Keep one dev module running: restart it when it exits on its own.

    python -m naas_abi_cli.cli.dev_supervisor [--restart on-failure] -- <command...>

`abi dev up` starts each `dev.modules` entry through this, in a process group
of its own. `abi dev down` signals the group: the module gets SIGTERM directly
(and can drain), the supervisor stops restarting and exits once it has.
Restarts back off from 1 s to 30 s, and back to 1 s after a run of a minute.
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, Literal, Protocol

Restart = Literal["on-failure", "always", "never"]
GRACE_SECONDS = 15.0  # a stopped module's time to drain before SIGTERM/SIGKILL


class _Stopped(Protocol):
    def is_set(self) -> bool: ...

    def wait(self, timeout: float) -> bool: ...


def _wait(child: Any, stopped: _Stopped, grace_seconds: float) -> int:
    while True:
        try:
            return child.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            if not stopped.is_set():
                continue
        # Stopped: the group signal reached the module too; let it drain first.
        try:
            return child.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            child.terminate()
        try:
            return child.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            child.kill()
            return child.wait()


def supervise(
    command: Sequence[str],
    *,
    restart: Restart = "on-failure",
    stopped: _Stopped,
    spawn: Callable[[Sequence[str]], Any] = subprocess.Popen,
    clock: Callable[[], float] = time.monotonic,
    initial_backoff: float = 1.0,
    max_backoff: float = 30.0,
    stable_seconds: float = 60.0,
    grace_seconds: float = GRACE_SECONDS,
    log: Callable[[str], None] = print,
) -> int:
    """Run ``command`` until it exits for good; its last exit code."""
    backoff = initial_backoff
    while True:
        started = clock()
        code = _wait(spawn(command), stopped, grace_seconds)
        if stopped.is_set():
            return code
        if restart == "never" or (restart == "on-failure" and code == 0):
            log(f"[abi dev] exited with code {code}")
            return code
        if clock() - started >= stable_seconds:
            backoff = initial_backoff
        log(f"[abi dev] exited with code {code}; restarting in {backoff:g}s")
        if stopped.wait(backoff):
            return code
        backoff = min(backoff * 2, max_backoff)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--restart", choices=("on-failure", "always", "never"), default="on-failure"
    )
    parser.add_argument("--initial-backoff", type=float, default=1.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")

    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    code = supervise(
        command,
        restart=args.restart,
        stopped=stopped,
        initial_backoff=args.initial_backoff,
        log=lambda line: print(line, flush=True),
    )
    return code if code >= 0 else 128 - code  # killed by a signal


if __name__ == "__main__":
    sys.exit(main())

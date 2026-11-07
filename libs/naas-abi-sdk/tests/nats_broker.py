"""A local ``nats-server`` with JetStream for the SDK's broker suites.

An open broker: who may do what on the broker is the engine's auth callout,
which these suites stand in for with the host's own checks (core runs the
callout end to end).
"""

from __future__ import annotations

import contextlib
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path


@contextlib.contextmanager
def running_broker(tmp_path: Path) -> Iterator[str]:
    """A ``nats-server -js`` on a free port; yields its URL."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    process = subprocess.Popen(
        [
            "nats-server",
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
            "-js",
            "-sd",
            str(tmp_path / "js"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.05)
        yield f"nats://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait(timeout=5)

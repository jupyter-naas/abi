"""A local ``nats-server`` for tests, without Docker."""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def nats_server_binary() -> str | None:
    return shutil.which("nats-server")


@contextmanager
def native_nats_server(
    workdir: Path, *, max_payload: int | None = None, jetstream: bool = False
) -> Iterator[str]:
    """Run ``nats-server`` on a free local port; yield its URL."""
    binary = nats_server_binary()
    if binary is None:
        raise RuntimeError("nats-server is not installed")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command = [binary, "-a", "127.0.0.1", "-p", str(port)]
    if max_payload is not None:
        config = workdir / "nats.conf"
        config.write_text(f"max_payload: {max_payload}\n")
        command += ["-c", str(config)]
    if jetstream:
        command += ["-js", "-sd", str(workdir / "jetstream")]
    with (workdir / "nats.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 5
        while True:
            if process.poll() is not None:
                raise RuntimeError("nats-server exited before accepting connections")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                if time.monotonic() > deadline:
                    raise RuntimeError("nats-server did not become ready") from None
                time.sleep(0.02)
        yield f"nats://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait(timeout=5)

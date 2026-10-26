"""Brokers as deployed, for the SDK's real-broker suites.

``open``: anyone connects with every right. ``module-user``: every client logs in,
and the suite connects as ``module``, within the engine's MODULE_PERMISSIONS
(naas_abi_core.engine.nats_permissions), as SDK modules do in a project. It needs
ABI core for that definition, so the SDK's isolated runs skip it.
"""

from __future__ import annotations

import contextlib
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

KINDS = ("open", "module-user")
PASSWORDS = {"abi": "nats-abi-tests", "module": "nats-module-tests"}


def config(kind: str) -> str:
    """nats.conf lines admitting the deployed users, or none for ``open``."""
    if kind == "open":
        return ""
    permissions = pytest.importorskip("naas_abi_core.engine.nats_permissions")
    return permissions.authorization_config(PASSWORDS)


def login(url: str, kind: str) -> str:
    """``url`` as the suite connects to it: logged in as ``module`` if users are on."""
    if kind == "open":
        return url
    return url.replace("nats://", f"nats://module:{PASSWORDS['module']}@", 1)


def as_engine(url: str) -> str:
    """``url`` logged in as ``abi`` instead (every right), for what an operator
    or the engine does in a test, such as deleting a stream."""
    module = f"module:{PASSWORDS['module']}@"
    return url.replace(module, f"abi:{PASSWORDS['abi']}@", 1)


def prepare(url: str, kind: str, project: str) -> None:
    """What the engine does at start in a project with modules: create the jobs
    stream and the claim-check store, which the module user may not create
    (naas_abi_core.engine.nats_permissions.prepare_module_streams)."""
    if kind == "open":
        return
    import asyncio

    asyncio.run(prepare_async(url, project))


async def prepare_async(url: str, project: str) -> None:
    """``prepare`` from a running event loop, whatever the broker (idempotent)."""
    import nats

    permissions = pytest.importorskip("naas_abi_core.engine.nats_permissions")
    nc = await nats.connect(as_engine(url))
    try:
        await permissions.prepare_module_streams(nc, project)
    finally:
        await nc.close()


async def connect(url: str):
    """A raw connection as a module makes it: logged in as ``module``, its inbox
    under ``_INBOX_MODULES`` (``_INBOX.>`` is the engine's), as ``Transport`` does."""
    import nats

    from naas_abi_sdk.transport import MODULE_INBOX_PREFIX

    options = {"inbox_prefix": MODULE_INBOX_PREFIX} if "nats://module:" in url else {}
    return await nats.connect(url, **options)


@contextlib.contextmanager
def running_broker(kind: str, tmp_path: Path, project: str) -> Iterator[str]:
    """A ``nats-server`` with JetStream, as ``kind`` is deployed, prepared for
    ``project``; yields the URL the suite connects with."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    conf = tmp_path / "nats.conf"
    conf.write_text(config(kind))
    process = subprocess.Popen(
        [
            "nats-server",
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
            "-c",
            str(conf),
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
        url = login(f"nats://127.0.0.1:{port}", kind)
        prepare(url, kind, project)
        yield url
    finally:
        process.terminate()
        process.wait(timeout=5)

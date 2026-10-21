"""Platform-admin operations through the real client and primary over a local
nats-server (no Docker): what the System app relies on."""

import shutil
import socket
import subprocess
import time

import pytest
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient import (
    SourceControlSecondaryAdapterNATSClient,
)
from naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient_test import (
    JWT_SECRET,
    _PrimaryAdapterServer,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    FileWrite,
    RepoNotFoundError,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def nats_url(tmp_path):
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("nats-server is not installed")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (tmp_path / "nats.log").open("w") as log:
        process = subprocess.Popen(
            [binary, "-a", "127.0.0.1", "-p", str(port)],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.01)
            else:
                pytest.fail("nats-server did not become ready")
            yield f"nats://127.0.0.1:{port}"
        finally:
            process.terminate()
            process.wait(timeout=5)


@pytest.fixture
def remote(nats_url):
    wrapped = InMemoryAdapter()
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = SourceControlSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret=JWT_SECRET,
        service_identity="api",
        timeout_seconds=10.0,
    )
    yield client, wrapped
    client.close()
    server.stop()


def test_delete_repo_round_trip(remote):
    client, wrapped = remote
    client.ensure_repo(owner="alice", name="proj")

    client.delete_repo(repo_id="alice/proj")

    assert wrapped.list_repos() == []
    with pytest.raises(RepoNotFoundError):
        client.delete_repo(repo_id="alice/proj")


def test_deleting_a_file_commits_the_removal(remote):
    client, _ = remote
    client.ensure_repo(owner="alice", name="proj")
    client.upsert_files(
        repo_id="alice/proj",
        files=[FileWrite("a.txt", "a"), FileWrite("b.txt", "b")],
        message="seed",
        branch="main",
    )

    client.upsert_files(
        repo_id="alice/proj",
        files=[FileWrite("a.txt", b"", delete=True)],
        message="remove a",
        branch="main",
    )

    paths = [e.path for e in client.list_contents(repo_id="alice/proj")]
    assert "a.txt" not in paths and "b.txt" in paths

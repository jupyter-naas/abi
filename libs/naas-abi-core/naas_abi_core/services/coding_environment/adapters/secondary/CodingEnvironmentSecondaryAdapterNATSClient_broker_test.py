"""Platform-admin listing through the real client and primary over a local
nats-server (no Docker): what the System app relies on."""

import shutil
import socket
import subprocess
import time

import pytest
from naas_abi_core.services.coding_environment.adapters.secondary.CodingEnvironmentSecondaryAdapterNATSClient import (
    CodingEnvironmentSecondaryAdapterNATSClient,
)
from naas_abi_core.services.coding_environment.adapters.secondary.CodingEnvironmentSecondaryAdapterNATSClient_test import (
    JWT_SECRET,
    _PrimaryAdapterServer,
)
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
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


def test_list_all_environments_round_trip(nats_url):
    wrapped = InMemoryAdapter()
    wrapped.provision(user_id="u-alice", template_id="tmpl-default", name="dev")
    wrapped.provision(user_id="u-bob", template_id="tmpl-default", name="api")
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = CodingEnvironmentSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret=JWT_SECRET,
        service_identity="api",
        timeout_seconds=10.0,
    )
    try:
        environments = client.list_all_environments()
    finally:
        client.close()
        server.stop()

    assert sorted((e.owner, e.name) for e in environments) == [
        ("u-alice", "dev"),
        ("u-bob", "api"),
    ]
    assert all(e.template == "tmpl-default" and e.created_at for e in environments)

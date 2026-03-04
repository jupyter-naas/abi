import time

import pytest
from naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph import Oxigraph
from naas_abi_core.services.triple_store.tests.triple_store__secondary_adapter__generic_test import (
    GenericTripleStoreSecondaryAdapterTest,
)
from testcontainers.core.container import DockerContainer


@pytest.fixture(scope="session")
def oxigraph_url():
    try:
        with DockerContainer("oxigraph/oxigraph:latest").with_exposed_ports(
            7878
        ) as container:
            host = container.get_container_host_ip()
            port = container.get_exposed_port(7878)
            base_url = f"http://{host}:{port}"

            deadline = time.time() + 45
            while time.time() < deadline:
                try:
                    Oxigraph(oxigraph_url=base_url, timeout=2)
                    break
                except Exception:
                    time.sleep(0.5)
            else:
                pytest.fail("Oxigraph container did not become ready in time")

            yield base_url
    except Exception as exc:
        pytest.skip(f"Docker/Testcontainers unavailable: {exc}")


@pytest.mark.integration
class TestOxigraphIntegration(GenericTripleStoreSecondaryAdapterTest):
    @pytest.fixture
    def adapter(self, oxigraph_url):
        return Oxigraph(oxigraph_url=oxigraph_url, timeout=10)

    @pytest.fixture
    def supports_named_graphs(self) -> bool:
        return True

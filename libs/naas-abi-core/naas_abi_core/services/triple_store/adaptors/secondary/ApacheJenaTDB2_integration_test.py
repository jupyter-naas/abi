import time

import pytest
from naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import (
    ApacheJenaTDB2,
)
from naas_abi_core.services.triple_store.tests.triple_store__secondary_adapter__generic_test import (
    GenericTripleStoreSecondaryAdapterTest,
)
from testcontainers.core.container import DockerContainer


@pytest.fixture(scope="session")
def jena_tdb2_url():
    try:
        with (
            DockerContainer("stain/jena-fuseki:5.1.0")
            .with_env("ADMIN_PASSWORD", "admin")
            .with_env("FUSEKI_DATASET_1", "ds")
            .with_exposed_ports(3030)
        ) as container:
            host = container.get_container_host_ip()
            port = container.get_exposed_port(3030)
            base_url = f"http://admin:admin@{host}:{port}/ds"

            deadline = time.time() + 45
            while time.time() < deadline:
                try:
                    ApacheJenaTDB2(jena_tdb2_url=base_url, timeout=2)
                    break
                except Exception:
                    time.sleep(0.5)
            else:
                pytest.fail("Apache Jena Fuseki container did not become ready in time")

            yield base_url
    except Exception as exc:
        pytest.skip(f"Docker/Testcontainers unavailable: {exc}")


@pytest.mark.integration
class TestApacheJenaTDB2Integration(GenericTripleStoreSecondaryAdapterTest):
    @pytest.fixture
    def adapter(self, jena_tdb2_url):
        return ApacheJenaTDB2(jena_tdb2_url=jena_tdb2_url, timeout=10)

    @pytest.fixture
    def supports_named_graphs(self) -> bool:
        return True

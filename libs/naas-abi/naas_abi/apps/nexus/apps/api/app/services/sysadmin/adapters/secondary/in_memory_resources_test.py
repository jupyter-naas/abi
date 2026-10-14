import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
    InMemoryResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    AdminAuditLogContract,
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures


def _seed() -> dict[str, bytes]:
    nested = {f"{fixtures.SEED_CONTAINER}/{k}": v for k, v in fixtures.SEED_NESTED.items()}
    return {**fixtures.SEED_ITEMS, **nested}


class TestInMemoryResources(ServiceResourcesContract):
    containers = True

    @pytest.fixture
    def resources(self):
        return InMemoryResources("object_storage", _seed())


class TestMaskedInMemoryResources(ServiceResourcesContract):
    masked = True

    @pytest.fixture
    def resources(self):
        return InMemoryResources("secret", fixtures.SEED_ITEMS, masked=True)


class TestInMemoryAuditLog(AdminAuditLogContract):
    @pytest.fixture
    def audit(self):
        return InMemoryAuditLog()

    @pytest.fixture
    def recorded(self, audit):
        return lambda: list(audit.records)

    @pytest.fixture
    def broken_audit(self):
        return InMemoryAuditLog(fail="disk full")

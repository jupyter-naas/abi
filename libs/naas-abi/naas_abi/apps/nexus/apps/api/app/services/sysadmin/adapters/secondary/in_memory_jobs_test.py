import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_jobs import (
    InMemoryJobCatalog,
    InMemoryJobRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    JobCatalogContract,
    JobRunStoreContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures


class TestInMemoryJobCatalog(JobCatalogContract):
    @pytest.fixture
    def expected(self):
        return fixtures.job_definitions()

    @pytest.fixture
    def catalog(self, expected):
        return InMemoryJobCatalog(expected)


class TestInMemoryJobRunStore(JobRunStoreContract):
    @pytest.fixture
    def store(self):
        return InMemoryJobRunStore(fixtures.job_runs())

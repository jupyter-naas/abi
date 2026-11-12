"""A module's dataset namespace is its own.

The SDK's default manifest grants a module its own namespace
(``${module.dataset_namespace}``), and for a module's account the namespace
``default`` names it: modules never share ``default``.
"""

from __future__ import annotations

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckLake import (
    DatasetSecondaryAdapterDuckLake,
)
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetNotFoundError,
    DatasetSpec,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_core.services.dataset.iam_catalog import CATALOG
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.modules import bind, dataset_namespace
from naas_abi_core.services.iam.policy import parse_policy_document
from naas_abi_sdk.module import ModuleDependencies
from naas_abi_sdk.permissions import default_manifest

COLUMNS = (ColumnSpec(name="email", type="string"),)


@pytest.fixture
def setup(tmp_path):
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    with as_service_account("engine"):
        iam.register_catalog(CATALOG)
    datasets = DatasetService(
        DatasetSecondaryAdapterDuckLake(
            catalog=f"sqlite:{tmp_path / 'catalog.sqlite'}",
            data_path=str(tmp_path / "data"),
        )
    )
    datasets.set_services(IEngine.Services(iam=iam))
    return iam, datasets


def _module(iam: IAMService, project: str, module_id: str) -> CallContext:
    """A module account holding the SDK's default manifest for datasets."""
    name = f"module/{project}/{module_id}"
    manifest = parse_policy_document(
        default_manifest(ModuleDependencies(services=("dataset",)))
    )
    with as_service_account("engine"):
        account = iam.create_service_account(name)
        policy = iam.create_policy(
            f"module-{project}-{module_id}", bind(manifest, project, module_id)
        )
        iam.attach_policy(policy.id, account.id)
    return CallContext(principal=service_account(name))


def test_default_dataset_namespace_keeps_each_modules_datasets_apart(setup):
    iam, datasets = setup
    acme = _module(iam, "acme", "crm")
    other = _module(iam, "other", "probe")
    with use_call_context(acme):
        created = datasets.create(
            DatasetSpec(name="customers", namespace="default", columns=COLUMNS)
        )
        datasets.write("customers", [{"email": "a@acme.example"}], namespace="default")
        assert created.namespace == dataset_namespace("acme", "crm")
        rows = datasets.query("SELECT email FROM customers", namespace="default").rows
        assert [row["email"] for row in rows] == ["a@acme.example"]

    with use_call_context(other):
        for attempt in (
            lambda: datasets.query("SELECT email FROM customers", namespace="default"),
            lambda: datasets.write("customers", [{"email": "x"}], namespace="default"),
            lambda: datasets.drop("customers", namespace="default"),
            lambda: datasets.describe("customers", namespace="default"),
        ):
            with pytest.raises(DatasetNotFoundError):
                attempt()
        # Named by its namespace, the other module's dataset stays out of reach.
        own = dataset_namespace("acme", "crm")
        with pytest.raises((DatasetNotFoundError, PermissionDeniedError)):
            datasets.query(f"SELECT email FROM {own}.customers", namespace="default")
        with pytest.raises((DatasetNotFoundError, PermissionDeniedError)):
            datasets.drop("customers", namespace=own)
        assert datasets.list() == []

    with use_call_context(acme):
        assert datasets.describe("customers").name == "customers"


def test_default_dataset_namespace_keeps_the_shared_one_out_of_a_modules_reach(setup):
    iam, datasets = setup
    with as_service_account("engine"):
        datasets.create(
            DatasetSpec(name="shared", namespace="default", columns=COLUMNS)
        )
    module = _module(iam, "acme", "crm")
    with use_call_context(module):
        with pytest.raises(DatasetNotFoundError):
            datasets.describe("shared", namespace="default")
        with pytest.raises((DatasetNotFoundError, PermissionDeniedError)):
            datasets.query('SELECT * FROM "default".shared', namespace="default")

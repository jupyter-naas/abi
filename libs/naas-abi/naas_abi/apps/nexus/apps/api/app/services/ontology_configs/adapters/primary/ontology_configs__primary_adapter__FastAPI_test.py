"""Per-workspace ontology enable/disable, end to end over the route handlers.

The routes are awaited directly with an in-memory persistence adapter;
``require_workspace_access`` is stubbed because authorization is covered by
the auth service's own tests and would otherwise need a live database.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    OntologyCatalogScope,
    filter_ontology_catalog,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
    OntologyFileItemData,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.adapters.primary import (
    ontology_configs__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.port import (
    OntologyConfigCreate,
    OntologyConfigCreateInput,
    OntologyConfigPersistencePort,
    OntologyConfigRecord,
    OntologyConfigUpdate,
    OntologyConfigUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.service import (
    OntologyConfigsService,
)

WORKSPACE = "ws-test"

EXAMPLE = OntologyFileItemData(
    name="Example Ontology",
    path="/repo/src/example/ontologies/modules/ExampleOntology.ttl",
    module_name="example",
    description="An example",
)
BFO = OntologyFileItemData(
    name="BFO Core",
    path="/repo/libs/naas-abi-core/naas_abi_core/modules/bfo/ontologies/modules/bfo-core.ttl",
    module_name="bfo",
)
CATALOG = [EXAMPLE, BFO]


class FakeOntologyService:
    """Stands in for the engine TTL scan, applying the scope the same way."""

    def __init__(self, files: list[OntologyFileItemData] = CATALOG) -> None:
        self.files = files

    async def list_ontology_files(
        self, catalog_scope: OntologyCatalogScope | None = None
    ) -> list[OntologyFileItemData]:
        return filter_ontology_catalog(self.files, catalog_scope)


class InMemoryOntologyConfigs(OntologyConfigPersistencePort):
    """In-memory stand-in for the Postgres secondary adapter."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], OntologyConfigRecord] = {}

    @staticmethod
    def _record(
        workspace_id: str, ontology_id: str, enabled: bool
    ) -> OntologyConfigRecord:
        now = datetime(2026, 9, 16, 12, 0, 0)
        return OntologyConfigRecord(
            id=f"ont-{ontology_id}",
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )

    async def list_by_workspace(self, workspace_id: str) -> list[OntologyConfigRecord]:
        return [r for (ws, _), r in self.rows.items() if ws == workspace_id]

    async def get(
        self, workspace_id: str, ontology_id: str
    ) -> OntologyConfigRecord | None:
        return self.rows.get((workspace_id, ontology_id))

    async def create(self, data: OntologyConfigCreateInput) -> OntologyConfigRecord:
        record = self._record(data.workspace_id, data.ontology_id, data.enabled)
        self.rows[(data.workspace_id, data.ontology_id)] = record
        return record

    async def update(
        self, workspace_id: str, ontology_id: str, updates: OntologyConfigUpdateInput
    ) -> OntologyConfigRecord | None:
        existing = self.rows.get((workspace_id, ontology_id))
        if existing is None:
            return None
        if updates.enabled is not None:
            existing.enabled = bool(updates.enabled)
        return existing

    async def delete(self, workspace_id: str, ontology_id: str) -> bool:
        return self.rows.pop((workspace_id, ontology_id), None) is not None


@pytest.fixture
def configs() -> OntologyConfigsService:
    return OntologyConfigsService(InMemoryOntologyConfigs())


@pytest.fixture
def ontology_service() -> FakeOntologyService:
    return FakeOntologyService()


@pytest.fixture(autouse=True)
def _allow_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(user_id: str, workspace_id: str) -> str:
        return "owner"

    monkeypatch.setattr(adapter, "require_workspace_access", _allow)


@pytest.fixture(autouse=True)
def _no_yaml_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to a workspace with no seed list; tests opt in explicitly."""
    from naas_abi.apps.nexus.apps.api.app.services.ontology_configs import scope

    async def _slug(workspace_id: str) -> str | None:
        return None

    monkeypatch.setattr(scope, "workspace_slug", _slug)


class _User:
    id = "user-1"


async def _list(ontology_service, configs, workspace_id=WORKSPACE):
    response = await adapter.list_ontology_catalog(
        workspace_id=workspace_id,
        current_user=_User(),
        ontology_service=ontology_service,
        configs_service=configs,
    )
    return {item.ontology_id: item for item in response.ontologies}


@pytest.mark.asyncio
async def test_catalog_lists_every_ontology_disabled_by_default(
    ontology_service, configs
) -> None:
    items = await _list(ontology_service, configs)
    assert set(items) == {"example:exampleontology.ttl", "bfo:bfo-core.ttl"}
    assert all(item.enabled is False for item in items.values())
    # Settings needs the path too: it is what ?ontology= and the sidebar use.
    assert items["bfo:bfo-core.ttl"].path == BFO.path


@pytest.mark.asyncio
async def test_patch_creates_row_when_missing_then_toggles(
    ontology_service, configs
) -> None:
    created = await adapter.update_ontology_config(
        workspace_id=WORKSPACE,
        ontology_id="bfo:bfo-core.ttl",
        updates=OntologyConfigUpdate(enabled=True),
        current_user=_User(),
        ontology_service=ontology_service,
        configs_service=configs,
    )
    assert created["enabled"] is True

    items = await _list(ontology_service, configs)
    assert items["bfo:bfo-core.ttl"].enabled is True
    assert items["example:exampleontology.ttl"].enabled is False

    disabled = await adapter.update_ontology_config(
        workspace_id=WORKSPACE,
        ontology_id="bfo:bfo-core.ttl",
        updates=OntologyConfigUpdate(enabled=False),
        current_user=_User(),
        ontology_service=ontology_service,
        configs_service=configs,
    )
    assert disabled["enabled"] is False
    assert (await _list(ontology_service, configs))["bfo:bfo-core.ttl"].enabled is False


@pytest.mark.asyncio
async def test_enabling_exposes_the_file_to_the_ontology_routes(
    ontology_service, configs
) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary import (
        ontology__primary_adapter__FastAPI as ontology_adapter,
    )
    from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
        OntologyPathNotFoundError,
    )
    from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.scope import (
        build_ontology_catalog_scope,
    )

    # Disabled: the per-path routes refuse it (surfaced as 404 by the routes).
    scope = await build_ontology_catalog_scope(WORKSPACE, configs)
    with pytest.raises(OntologyPathNotFoundError):
        await ontology_adapter._require_catalog_path(BFO.path, scope, ontology_service)

    await adapter.update_ontology_config(
        workspace_id=WORKSPACE,
        ontology_id="bfo:bfo-core.ttl",
        updates=OntologyConfigUpdate(enabled=True),
        current_user=_User(),
        ontology_service=ontology_service,
        configs_service=configs,
    )

    scope = await build_ontology_catalog_scope(WORKSPACE, configs)
    await ontology_adapter._require_catalog_path(BFO.path, scope, ontology_service)
    # The still-disabled sibling stays out of reach.
    with pytest.raises(OntologyPathNotFoundError):
        await ontology_adapter._require_catalog_path(
            EXAMPLE.path, scope, ontology_service
        )
    listed = await ontology_service.list_ontology_files(catalog_scope=scope)
    assert [item.path for item in listed] == [BFO.path]


@pytest.mark.asyncio
async def test_unknown_ontology_id_is_rejected(ontology_service, configs) -> None:
    with pytest.raises(HTTPException) as exc:
        await adapter.update_ontology_config(
            workspace_id=WORKSPACE,
            ontology_id="nope:missing.ttl",
            updates=OntologyConfigUpdate(enabled=True),
            current_user=_User(),
            ontology_service=ontology_service,
            configs_service=configs,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_then_duplicate_conflicts(ontology_service, configs) -> None:
    await adapter.create_ontology_config(
        workspace_id=WORKSPACE,
        body=OntologyConfigCreate(ontology_id="bfo:bfo-core.ttl", enabled=True),
        current_user=_User(),
        ontology_service=ontology_service,
        configs_service=configs,
    )
    with pytest.raises(HTTPException) as exc:
        await adapter.create_ontology_config(
            workspace_id=WORKSPACE,
            body=OntologyConfigCreate(ontology_id="bfo:bfo-core.ttl", enabled=True),
            current_user=_User(),
            ontology_service=ontology_service,
            configs_service=configs,
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_delete_reverts_to_the_default(ontology_service, configs) -> None:
    await adapter.update_ontology_config(
        workspace_id=WORKSPACE,
        ontology_id="bfo:bfo-core.ttl",
        updates=OntologyConfigUpdate(enabled=True),
        current_user=_User(),
        ontology_service=ontology_service,
        configs_service=configs,
    )
    await adapter.delete_ontology_config(
        workspace_id=WORKSPACE,
        ontology_id="bfo:bfo-core.ttl",
        current_user=_User(),
        ontology_service=ontology_service,
        configs_service=configs,
    )
    assert (await _list(ontology_service, configs))["bfo:bfo-core.ttl"].enabled is False


@pytest.mark.asyncio
async def test_catalog_without_workspace_reports_disabled(
    ontology_service, configs
) -> None:
    """No workspace means no per-workspace state to report."""
    response = await adapter.list_ontology_catalog(
        workspace_id=None,
        current_user=_User(),
        ontology_service=ontology_service,
        configs_service=configs,
    )
    assert len(response.ontologies) == 2
    assert all(item.enabled is False for item in response.ontologies)

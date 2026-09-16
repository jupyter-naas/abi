"""OntologyConfigsService — per-workspace ontology enable/disable.

Catalog discovery lives in ``services/ontology`` (the engine module TTL
scan); this service owns only the per-workspace configuration of that
catalog, exactly as ``AppsService`` does for marketplace apps.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.port import (
    OntologyConfigCreateInput,
    OntologyConfigPersistencePort,
    OntologyConfigRecord,
    OntologyConfigUpdateInput,
)


class OntologyAlreadyConfiguredError(Exception):
    """Raised when creating a config that already exists for (workspace, ontology)."""


class OntologyConfigsService:
    """Per-workspace config for reference (module TTL) ontologies."""

    def __init__(self, adapter: OntologyConfigPersistencePort | None = None):
        self.adapter = adapter

    def _require_adapter(self) -> OntologyConfigPersistencePort:
        if self.adapter is None:
            raise RuntimeError(
                "OntologyConfigsService has no persistence adapter configured"
            )
        return self.adapter

    async def list_ontology_configs(
        self, workspace_id: str
    ) -> list[OntologyConfigRecord]:
        if self.adapter is None:
            return []
        return await self.adapter.list_by_workspace(workspace_id)

    async def get_ontology_config(
        self, workspace_id: str, ontology_id: str
    ) -> OntologyConfigRecord | None:
        if self.adapter is None:
            return None
        return await self.adapter.get(workspace_id, ontology_id)

    async def create_ontology_config(
        self, data: OntologyConfigCreateInput
    ) -> OntologyConfigRecord:
        adapter = self._require_adapter()
        existing = await adapter.get(data.workspace_id, data.ontology_id)
        if existing is not None:
            raise OntologyAlreadyConfiguredError(
                f"Ontology config for ({data.workspace_id}, {data.ontology_id}) "
                "already exists"
            )
        return await adapter.create(data)

    async def update_ontology_config(
        self,
        workspace_id: str,
        ontology_id: str,
        updates: OntologyConfigUpdateInput,
    ) -> OntologyConfigRecord | None:
        adapter = self._require_adapter()
        return await adapter.update(workspace_id, ontology_id, updates)

    async def delete_ontology_config(
        self, workspace_id: str, ontology_id: str
    ) -> bool:
        adapter = self._require_adapter()
        return await adapter.delete(workspace_id, ontology_id)

    async def get_enabled_states(self, workspace_id: str) -> dict[str, bool]:
        """Return ``{ontology_id: enabled}`` for every record in ``workspace_id``.

        Ontologies without a stored record are absent from the result;
        callers default missing entries to ``False`` (disabled by default).
        """
        records = await self.list_ontology_configs(workspace_id)
        return {r.ontology_id: r.enabled for r in records}

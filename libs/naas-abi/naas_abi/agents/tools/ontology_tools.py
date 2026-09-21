"""OntologyAgent tools for Nexus Ontology.

Same data as ``/api/ontology`` (``/ontologies``, ``/classes``,
``/relationships``, ``/overview/stats``), scoped the same way: workspace
membership, then the workspace seed's ``ontologies:`` list when it declares
one (``None`` keeps the full engine catalog). The ontology open on the page
(``?ontology=<path>``) arrives as the open feature resource (kind
``ontology``), so tools default to it.

Writes (create entity/relationship, delete, import) are not exposed here:
those endpoints are not workspace-scoped, so the agent explains the UI flow
instead of writing to a shared store on the user's behalf.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.feature.runtime import (
    clip,
    guarded,
    jsonable,
    matches,
    require_member,
    run,
    run_db,
    tool_context,
    workspace_seed,
)

ONTOLOGY_RESOURCE_KIND = "ontology"
_FEATURE = "Ontology"
_MAX_ROWS = 60
_GUIDELINES_RE = re.compile(
    r"<operating_guidelines>(.*?)</operating_guidelines>", re.DOTALL
)


def _service() -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.ontology.service import (
        OntologyService,
    )
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

    try:
        return ServiceRegistry.instance().ontology
    except RuntimeError:
        return OntologyService()


def _catalog_refs(user_id: str, workspace_id: str) -> list[str] | None | dict[str, str]:
    """Seed ontology refs, None for the full catalog, or an access error."""

    async def _run(db: Any) -> Any:
        role = await require_member(db, user_id, workspace_id)
        if isinstance(role, dict):
            return role
        seed = await workspace_seed(db, workspace_id)
        refs = getattr(seed, "ontologies", None) if seed is not None else None
        return None if refs is None else list(refs)

    return run_db(_run)


def _resolve_path(ontology_path: str, files: list[Any]) -> str | dict[str, str] | None:
    """Explicit path, then the open ontology. Must be in the workspace catalog."""
    wanted = (ontology_path or "").strip() or active_feature_resource_id(
        ONTOLOGY_RESOURCE_KIND
    )
    if not wanted:
        return None
    paths = {f.path for f in files}
    if wanted in paths:
        return wanted
    by_name = next((f.path for f in files if f.name.lower() == wanted.lower()), None)
    if by_name:
        return by_name
    return {
        "error": f"Ontology not in this workspace catalog: {wanted}. See list_workspace_ontologies."
    }


def _item(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "parent": item.parent_name,
        "description": clip(item.description, 200),
    }


def ontology_tools() -> list[BaseTool]:
    @tool
    def list_workspace_ontologies(query: str = "") -> Any:
        """List the ontology files in this workspace's catalog.

        Rows: name, path (use it as ontology_path), module, description,
        imports. Filter with query.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        open_path = active_feature_resource_id(ONTOLOGY_RESOURCE_KIND)

        def _run() -> Any:
            refs = _catalog_refs(user_id, workspace_id)
            if isinstance(refs, dict):
                return refs
            files = run(_service().list_ontology_files(catalog_refs=refs))
            rows = [
                {
                    "name": f.name,
                    "path": f.path,
                    "module": f.module_name,
                    "description": clip(f.description, 200),
                    "imports": list(f.imports)[:10],
                }
                for f in files
                if matches(query, f.name, f.path, f.description, f.module_name)
            ]
            return {
                "scoped_by_workspace_seed": refs is not None,
                "open_ontology": open_path,
                "total": len(rows),
                "ontologies": rows[:_MAX_ROWS],
            }

        return guarded(_FEATURE, _run)

    @tool
    def get_ontology_overview(ontology_path: str = "") -> Any:
        """Element counts for one ontology (classes, object/data properties,
        individuals, imports). Omit ontology_path to use the open ontology;
        with none open, returns the totals across the workspace catalog."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx

        def _run() -> Any:
            refs = _catalog_refs(user_id, workspace_id)
            if isinstance(refs, dict):
                return refs
            service = _service()
            files = run(service.list_ontology_files(catalog_refs=refs))
            path = _resolve_path(ontology_path, files)
            if isinstance(path, dict):
                return path
            if path is None:
                return jsonable(run(service.get_all_overview_stats(catalog_refs=refs)))
            return jsonable(run(service.get_overview_stats(ontology_path=path)))

        return guarded(_FEATURE, _run)

    def _list(kind: str, ontology_path: str, query: str) -> Any:
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx

        def _run() -> Any:
            refs = _catalog_refs(user_id, workspace_id)
            if isinstance(refs, dict):
                return refs
            service = _service()
            files = run(service.list_ontology_files(catalog_refs=refs))
            path = _resolve_path(ontology_path, files)
            if isinstance(path, dict):
                return path
            lister = (
                service.list_classes if kind == "classes" else service.list_relations
            )
            items = run(lister(ontology_path=path, catalog_refs=refs))
            rows = [
                _item(i) for i in items if matches(query, i.name, i.id, i.description)
            ]
            return {
                "ontology_path": path,
                "total": len(rows),
                kind: rows[:_MAX_ROWS],
                "truncated": len(rows) > _MAX_ROWS,
            }

        return guarded(_FEATURE, _run)

    @tool
    def list_ontology_classes(ontology_path: str = "", query: str = "") -> Any:
        """OWL classes of an ontology (or the whole catalog when none is open).

        Rows: id (IRI), name, parent, description. Filter with query.
        """
        return _list("classes", ontology_path, query)

    @tool
    def list_ontology_relations(ontology_path: str = "", query: str = "") -> Any:
        """Object properties (relations) of an ontology, same shape as classes."""
        return _list("relations", ontology_path, query)

    @tool
    def get_bfo_modeling_guidelines() -> str:
        """House rules for modeling a new class or property (BFO 7 Buckets),
        from the Ontology Engineer agent. Use before proposing Turtle."""
        from naas_abi.agents.OntologyEngineerAgent import OntologyEngineerAgent

        match = _GUIDELINES_RE.search(OntologyEngineerAgent.system_prompt)
        return match.group(1).strip() if match else OntologyEngineerAgent.system_prompt

    return [
        list_workspace_ontologies,
        get_ontology_overview,
        list_ontology_classes,
        list_ontology_relations,
        get_bfo_modeling_guidelines,
    ]

"""Module scopes: what modules expose, grantable per workspace one item at a time.

Two kinds, both marked ``module_scope`` in their catalog so the built-in
viewer and member roles never reach them (``roles.py``) and the UI finds them:

* **Automatic.** Every agent, app, workflow and pipeline of every module,
  engine or remote, is a resource of the ``module`` catalog below:
  ``abi:<org>:<ws>:module:<type>/<module>/<name>``. ``<module>`` is the
  module's stable identifier (``module_key``): an engine module's configured
  path (``naas_abi``, ``naas_abi_marketplace.ai.claude``), the same in every
  install; a remote module's id (``acme.people``), the same across restarts.
* **Declared.** A module may ship a catalog of its own (``iam_catalog.yaml``
  beside its module class): resource types and actions under the module's own
  service name (``module_service``). The engine registers an engine module's
  at load; a remote module's travels with its manifest and is registered when
  the manifest is approved. ``module_catalog`` checks one.

The name is placed in the workspace of the call, never looked up: a module
scope is a permission to use something in a workspace, not data a workspace
owns. A user claiming another workspace gets what they hold there, which is
what using it there needs (``AGENTS.md``, "Module scopes").
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ActionSpec,
    CatalogError,
    ResourceType,
)
from naas_abi_core.services.iam.names import NONE, resource_name

SERVICE = "module"
VERSION = 1

AGENT = "agent"
APP = "app"
WORKFLOW = "workflow"
PIPELINE = "pipeline"
TYPES = (AGENT, APP, WORKFLOW, PIPELINE)

# The action that uses each type, and the one that reads the caller's own runs.
USE_ACTION: dict[str, str] = {
    AGENT: "UseAgent",
    APP: "OpenApp",
    WORKFLOW: "RunWorkflow",
    PIPELINE: "RunPipeline",
}
RUNS_ACTION: dict[str, str] = {
    WORKFLOW: "ReadWorkflowRuns",
    PIPELINE: "ReadPipelineRuns",
}

# A module's own catalog, beside its module class.
CATALOG_FILE = "iam_catalog.yaml"


def _type(name: str, description: str) -> ResourceType:
    return ResourceType(name, id="path", module_scope=True, description=description)


def _action(name: str, level: str, type_name: str, description: str) -> ActionSpec:
    return ActionSpec(
        name=name,
        level=level,  # type: ignore[arg-type]
        resource_types=(type_name,),
        description=description,
    )


CATALOG = ActionCatalog(
    service=SERVICE,
    version=VERSION,
    resource_types=(
        _type(
            AGENT, "agent/<module>/<name>: an agent of a module, used in a workspace."
        ),
        _type(APP, "app/<module>/<name>: an app of a module, opened in a workspace."),
        _type(
            WORKFLOW,
            "workflow/<module>/<name>: a workflow of a module, run in a workspace.",
        ),
        _type(
            PIPELINE,
            "pipeline/<module>/<name>: a pipeline of a module, run in a workspace.",
        ),
    ),
    actions=(
        _action(
            "UseAgent", "write", AGENT, "Chat with the agent, call it through /v1."
        ),
        _action("OpenApp", "read", APP, "Open the app, its links and grants."),
        _action("RunWorkflow", "write", WORKFLOW, "Start the workflow."),
        _action(
            "ReadWorkflowRuns", "read", WORKFLOW, "Read one's own runs of the workflow."
        ),
        _action("RunPipeline", "write", PIPELINE, "Start the pipeline."),
        _action(
            "ReadPipelineRuns", "read", PIPELINE, "Read one's own runs of the pipeline."
        ),
    ),
)


def scope_resource(
    type_name: str,
    module: str,
    name: str,
    *,
    org: str = NONE,
    workspace: str = NONE,
) -> str:
    """``abi:<org>:<ws>:module:<type>/<module>/<name>``."""
    if type_name not in TYPES:
        raise ValueError(f"Unknown module scope type {type_name!r}")
    return resource_name(
        SERVICE, type_name, [module, name], kind="path", org=org, workspace=workspace
    )


def module_pattern(type_name: str, module: str, *, scope: str = "${scope}") -> str:
    """Every ``type_name`` of ``module`` at a scope (a policy's resource pattern)."""
    prefix = scope_resource(type_name, module, "x").rsplit("/", 1)[0]
    return f"{scope}:{prefix.split(':', 3)[3]}/*"


# -- declared catalogs ------------------------------------------------------------

_NOT_SERVICE = re.compile(r"[^a-z0-9_]+")


def module_service(module: str) -> str:
    """The service name of ``module``'s own catalog: its identifier in lower case,
    every other character an underscore (``acme.people`` is ``acme_people``)."""
    service = _NOT_SERVICE.sub("_", module.lower()).strip("_")
    if not service:
        raise CatalogError(f"Module {module!r} has no usable catalog name")
    return service if service[0].isalpha() else f"m_{service}"


def reserved_services() -> frozenset[str]:
    """Catalog names no module may take: the kernel services', IAM's, Nexus's and
    the module scopes'."""
    from naas_abi_core.services.iam.kernel_catalogs import kernel_catalogs

    return frozenset({"iam", "nexus", SERVICE, *(c.service for c in kernel_catalogs())})


class ModuleCatalogError(CatalogError):
    """A module's catalog that cannot be registered."""


def module_catalog(
    data: ActionCatalog | Mapping[str, Any], module: str
) -> ActionCatalog:
    """``module``'s declared catalog, checked and owned by it.

    Its ``service`` is ``module_service(module)`` (filled in when absent, refused
    when it names anything else: a kernel service, ``nexus``, ``module`` or
    another module); every resource type is a module scope placed in a
    workspace (``module_scope`` is set for it).
    """
    raw: dict[str, Any] = (
        data.to_dict() if isinstance(data, ActionCatalog) else dict(data)
    )
    own = module_service(module)
    service = str(raw.get("service") or own)
    if service in reserved_services():
        raise ModuleCatalogError(
            f"Module {module!r} may not declare catalog {service!r}: it is reserved"
        )
    if service != own:
        raise ModuleCatalogError(
            f"Module {module!r} declares catalog {service!r}: its own is {own!r}"
        )
    owner = str(raw.get("module") or module)
    if owner != module:
        raise ModuleCatalogError(
            f"Module {module!r} declares a catalog of module {owner!r}"
        )
    types: list[dict[str, Any]] = []
    for item in raw.get("resource_types") or ():
        if not isinstance(item, Mapping):
            raise ModuleCatalogError(f"Malformed resource type {item!r}")
        if item.get("placement", "placed") != "placed":
            raise ModuleCatalogError(
                f"Resource type {item.get('name')!r}: a module's resources are "
                "placed in the workspace of the call"
            )
        types.append({**item, "module_scope": True})
    return ActionCatalog.from_dict(
        {
            **raw,
            "service": service,
            "version": raw.get("version", 1),
            "resource_types": types,
            "module": module,
        }
    )


def load_module_catalog(directory: str | Path, module: str) -> ActionCatalog | None:
    """The catalog in ``directory/iam_catalog.yaml``, checked; None without one."""
    path = Path(directory) / CATALOG_FILE
    if not path.is_file():
        return None
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ModuleCatalogError(f"{path}: a catalog is a mapping")
    return module_catalog(data, module)


def declared_resource(
    catalog: ActionCatalog,
    type_name: str,
    parts: str | Sequence[str],
    *,
    org: str = NONE,
    workspace: str = NONE,
) -> str:
    """A resource of a module's own catalog, at the workspace of the call."""
    declared = catalog.resource_type(type_name)
    if declared is None:
        raise ValueError(f"{catalog.service} declares no resource type {type_name!r}")
    return resource_name(
        catalog.service,
        type_name,
        parts,
        kind=declared.id,
        org=org,
        workspace=workspace,
    )


def register_module_catalogs(iam: Any, modules: Iterable[Any]) -> list[str]:
    """Register the catalog each engine module declares (``BaseModule.iam_catalog``),
    as the caller (the engine, while it loads); the services registered."""
    registered: list[str] = []
    for module in modules:
        catalog = getattr(module, "iam_catalog", None)
        if catalog is None:
            continue
        iam.register_catalog(catalog)
        registered.append(catalog.service)
    return registered

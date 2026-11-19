"""A module's permission manifest: what it asks an admin to approve.

The manifest is a policy document (``version`` and ``statements`` of
``effect``, ``actions`` and ``resources``). A module declares it as
``BaseModule.permissions``, or in ``permissions.yaml`` beside the module's
code; otherwise it defaults from ``ModuleDependencies``. A default grant stays
in the module's own namespace, on the platform: it never reaches a container
(an organization's or a workspace's data), nor another module's names. A module
that needs more names it in a manifest of its own, where the admin sees it.

* ``document``: everything on the module's own namespace, ``${module.id}``;
* ``secret``: the secrets named ``<module id>/...``; never every secret;
* ``dataset``: the module's own namespace, ``${module.dataset_namespace}``
  (what the namespace ``default`` names for a module), without unchecked SQL
  (``dataset:QueryUnchecked`` is denied);
* ``cache`` and ``keyvalue``: the keys named ``<module id>/...``;
* ``object_storage``: the objects under the prefix ``<module id>/``;
* ``vector_store``: the collections named ``<module id>~...`` (a collection
  name is one identifier: ``~`` is the separator no module id holds);
* ``triple_store``: every action on its own graphs (``module_graph``: IRIs
  under ``http://ontology.naas.ai/graph/module/<module id>/``) and its own
  views (``<module id>/...``), reading the schema graph, and its own
  ontologies only (``LoadSchema`` on ``schema/module/<module id>/...``);
* ``email``: sending only. The platform keeps a copy of the mail it sends,
  sign-in codes included, so listing, reading and deleting kept messages is
  asked for by name;
* ``source_control``: every action but ``AddCollaborator``, an admin action
  that grants a forge user access to any repository (name it to ask for it);
* any other service it declares (``event`` among them): every action of that
  service on what the platform holds, never on what a container holds;
* the modules it depends on: their agents, models and apps, and the runs it
  starts (never the built-in identity provider's ``admin`` app);
* its own jobs, when it declares some, each by name (``@job`` and ``@workflow``
  methods, and the ``workflow.<slug>`` / ``pipeline.<slug>`` of each
  ``Workflow`` and ``Pipeline`` class): the broker gives the module the
  consumers of the jobs its manifest names, and only those. A job declared in
  ``on_load`` is not known here: a module declaring one writes its manifest.

``${module.id}``, ``${module.project}`` and ``${module.dataset_namespace}`` are
bound when the manifest is approved. Bus topics have no default: a module using the bus declares them,
``bus:*`` on ``abi:bus:topic/<topic>``.

A module may also declare actions of its own (``BaseModule.iam_catalog``, or
``iam_catalog.yaml`` beside the module): a catalog of resource types and
actions under the module's own service name (``catalog_service``). It travels
with the manifest under ``catalog``, is part of what the admin approves, and is
registered by the approval. The module enforces its actions with
``BaseModule.require_action``; users get them through policies, never through
the viewer and member roles.
"""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from naas_abi_sdk.module import BaseModule, ModuleDependencies

POLICY_VERSION = "2026-10-13"
MANIFEST_FILE = "permissions.yaml"
CATALOG_FILE = "iam_catalog.yaml"
_NOT_SERVICE = re.compile(r"[^a-z0-9_]+")
_ALIASES = {"kv": "keyvalue", "events": "event"}


def _anywhere(rest: str) -> tuple[str, str]:
    """``rest`` at the platform and in any container (core's ``names.anywhere``):
    ``abi:<rest>`` and ``abi:*/<rest>``. For Denies only: a default never
    allows anything in a container."""
    return (f"abi:{rest}", f"abi:*/{rest}")


# The IRIs of a module's own graphs, and the schema graph's (both encoded, as a
# graph's id is: its IRI, every character outside RFC 3986 unreserved escaped).
MODULE_GRAPHS = "http://ontology.naas.ai/graph/module/"
_MODULE_GRAPHS_ID = "http%3A%2F%2Fontology.naas.ai%2Fgraph%2Fmodule%2F"
_SCHEMA_GRAPH_ID = "http%3A%2F%2Fontology.naas.ai%2Fgraph%2Fschema"


def module_graph(module_id: str, name: str) -> str:
    """The IRI of the module's own graph ``name``, which the default grants."""
    if not name or "/" in name:
        raise ValueError(f"A graph name is one non-empty segment: {name!r}")
    return f"{MODULE_GRAPHS}{module_id}/{name}"


_OWN_NAMESPACES = {
    "document": (
        "abi:document:namespace/${module.id}",
        "abi:document:collection/${module.id}/*",
        "abi:document:document/${module.id}/*",
    ),
    "secret": ("abi:secret:secret/${module.id}%2F*",),
    # A dataset namespace is an identifier, which a module id need not be: the
    # module's own is derived from its project and id when it is approved.
    "dataset": (
        "abi:dataset:namespace/${module.dataset_namespace}",
        "abi:dataset:dataset/${module.dataset_namespace}/*",
    ),
    "cache": ("abi:cache:key/${module.id}%2F*",),
    "keyvalue": ("abi:keyvalue:key/${module.id}%2F*",),
    "object_storage": ("abi:object_storage:object/${module.id}/*",),
    "vector_store": (
        "abi:vector_store:collection/${module.id}~*",
        "abi:vector_store:vector/${module.id}~*",
    ),
    # Its own graphs and views; the schemas it loads are its own (``OwnOntologies``).
    "triple_store": (
        f"abi:triple_store:graph/{_MODULE_GRAPHS_ID}${{module.id}}%2F*",
        "abi:triple_store:view/${module.id}%2F*",
    ),
}
# What a service grants besides its default statement: (sid, actions, resources).
_ALSO = {
    "triple_store": (
        (
            "ReadSchema",
            (
                "triple_store:Get",
                "triple_store:GetSubjectGraph",
                "triple_store:Query",
                "triple_store:QueryStream",
                "triple_store:Export",
            ),
            (f"abi:triple_store:graph/{_SCHEMA_GRAPH_ID}",),
        ),
        (
            "OwnOntologies",
            ("triple_store:LoadSchema",),
            ("abi:triple_store:schema/module/${module.id}/*",),
        ),
    ),
}


# What a default grant of a service is limited to, where "every action" is
# too much to approve unread.
_ACTIONS = {"email": ("email:Send",)}
# Actions a default grant of ``<service>:*`` never includes: a Deny.
_NEVER = {
    "source_control": ("source_control:AddCollaborator",),
    # SQL the query check cannot vouch for reads the engine host's files.
    "dataset": ("dataset:QueryUnchecked",),
}


def _statement(sid: str, actions: list[str], resources: list[str]) -> dict[str, Any]:
    return {"sid": sid, "effect": "Allow", "actions": actions, "resources": resources}


def _sid(service: str) -> str:
    return "".join(part.title() for part in service.split("_"))


def default_manifest(
    dependencies: ModuleDependencies, *, jobs: bool | Iterable[str] = ()
) -> dict[str, Any]:
    """``jobs``: the names of the module's jobs (``True``: every job, which
    lets it trigger them but host none behind the broker's auth callout)."""
    statements: list[dict[str, Any]] = []
    services = sorted(
        {_ALIASES.get(s, s) for s in dependencies.services} - {"bus", "iam"}
    )
    for service in services:
        # Any other service: what the platform holds, never a container.
        resources = _OWN_NAMESPACES.get(service, (f"abi:{service}:*",))
        statements.append(
            _statement(
                f"Use{_sid(service)}",
                list(_ACTIONS.get(service, (f"{service}:*",))),
                list(resources),
            )
        )
        for sid, actions, resources in _ALSO.get(service, ()):
            statements.append(_statement(sid, list(actions), list(resources)))
        if service in _NEVER:
            statements.append(
                {
                    "sid": f"No{_sid(service)}Admin",
                    "effect": "Deny",
                    "actions": list(_NEVER[service]),
                    "resources": list(_anywhere(f"{service}:*")),
                }
            )
    if dependencies.modules:
        project = "${module.project}"
        reach = []
        for module_id in dependencies.modules:
            reach += [
                f"abi:discovery:module/{project}/{module_id}",
                f"abi:discovery:agent/{project}/{module_id}/*",
                f"abi:discovery:model/{project}/{module_id}/*",
                f"abi:discovery:app/{project}/{module_id}/*",
            ]
        statements.append(
            _statement(
                "UseDependencies",
                [
                    "discovery:ListModules",
                    "discovery:GetModule",
                    "discovery:ListAgents",
                    "discovery:InvokeAgent",
                    "discovery:ChatModel",
                    "discovery:OpenApp",
                ],
                reach,
            )
        )
        if "idp" in dependencies.modules:
            # The identity provider's admin app (create users, groups and
            # clients) is for the platform's provisioning: depending on the
            # module is not asking for it (name it in a manifest to ask).
            statements.append(
                {
                    "sid": "NoIdentityProviderAdmin",
                    "effect": "Deny",
                    "actions": ["discovery:OpenApp"],
                    "resources": [f"abi:discovery:app/{project}/idp/admin"],
                }
            )
        statements.append(
            _statement(
                "FollowOwnRuns",
                ["discovery:GetAgentRun", "discovery:CancelAgentRun"],
                # Its own runs, and those of the user it acts for: a run started
                # for a user is that user's.
                [
                    "abi:discovery:run/${principal.id}/*",
                    "abi:discovery:run/${user.id}/*",
                ],
            )
        )
    names = ["*"] if jobs is True else sorted(set(jobs or ()))
    if names:
        statements.append(
            _statement(
                "OwnJobs",
                [
                    "discovery:ListJobs",
                    "discovery:TriggerJob",
                    "discovery:ScheduleJob",
                    "discovery:ListJobRuns",
                    "discovery:GetJobRun",
                    "discovery:CancelJobRun",
                ],
                [
                    *(
                        f"abi:discovery:job/${{module.project}}/${{module.id}}/{name}"
                        for name in names
                    ),
                    "abi:discovery:job_run/${module.project}/${module.id}/*",
                ],
            )
        )
    return {"version": POLICY_VERSION, "statements": statements}


def module_manifest(module_type: type[BaseModule]) -> dict[str, Any]:
    """The manifest ``module_type`` submits for approval, with its catalog."""
    manifest = _policy_manifest(module_type)
    catalog = module_catalog(module_type)
    if catalog is not None:
        manifest["catalog"] = catalog
    return manifest


def _policy_manifest(module_type: type[BaseModule]) -> dict[str, Any]:
    declared = getattr(module_type, "permissions", None)
    if declared is not None:
        return _document(declared, f"{module_type.__name__}.permissions")
    found = _manifest_file(module_type)
    if found is not None:
        return _document(_load_yaml(found), str(found))
    jobs = [job.name for job in getattr(module_type, "jobs", ())]  # @job included
    jobs += _process_workflows(module_type)
    return default_manifest(module_type.get_dependencies(), jobs=jobs)


def catalog_service(module_id: str) -> str:
    """The service name of a module's own catalog: its id in lower case, every
    other character an underscore (``acme.people`` is ``acme_people``). The
    engine's rule (core ``services/iam/module_scopes.module_service``)."""
    service = _NOT_SERVICE.sub("_", module_id.lower()).strip("_")
    if not service:
        raise ValueError(f"Module {module_id!r} has no usable catalog name")
    return service if service[0].isalpha() else f"m_{service}"


def module_catalog(module_type: type[BaseModule]) -> dict[str, Any] | None:
    """The catalog ``module_type`` declares: ``iam_catalog``, else
    ``iam_catalog.yaml`` beside the module, else None. Its ``service`` is the
    module's own (filled in); IAM checks the rest when the manifest is sent."""
    declared = getattr(module_type, "iam_catalog", None)
    if declared is None:
        found = _beside(module_type, CATALOG_FILE)
        declared = _load_yaml(found) if found is not None else None
    if declared is None:
        return None
    if not isinstance(declared, Mapping):
        raise TypeError(f"{module_type.__name__}: a catalog is a mapping")
    catalog = dict(declared)
    catalog.setdefault("service", catalog_service(module_identity(module_type)))
    catalog.setdefault("version", 1)
    return catalog


def module_identity(module_type: type) -> str:
    """The module id a module runs as: ``module_id``, else its Python module."""
    return getattr(module_type, "module_id", None) or module_type.__module__


def _process_workflows(module_type: type[BaseModule]) -> list[str]:
    """The durable workflow of each ``Workflow`` and ``Pipeline`` class, which
    the module declares when it starts (``workflow.<slug>``, ``pipeline.<slug>``).
    A job declared in ``on_load`` is known only at run time: name it in a
    manifest of the module's own."""
    from naas_abi_sdk.jobs import process_workflow_name

    found = []
    for kind, classes in (
        ("workflow", getattr(module_type, "get_workflow_classes", dict)()),
        ("pipeline", getattr(module_type, "get_pipeline_classes", dict)()),
    ):
        found += [process_workflow_name(kind, name) for name in sorted(classes)]
    return found


def _manifest_file(module_type: type) -> Path | None:
    return _beside(module_type, MANIFEST_FILE)


def _beside(module_type: type, name: str) -> Path | None:
    try:
        source = inspect.getfile(module_type)
    except (TypeError, OSError):
        return None
    candidate = Path(source).resolve().parent / name
    return candidate if candidate.is_file() else None


def _load_yaml(path: Path) -> Any:
    try:
        import yaml
    except ModuleNotFoundError:  # JSON is YAML: read it without PyYAML
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}: install PyYAML to read it, or write it as JSON"
            ) from exc
    return yaml.safe_load(path.read_text())


def _document(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("statements"), list):
        raise TypeError(f"{where}: a manifest is a policy document with statements")
    document = dict(value)
    document.setdefault("version", POLICY_VERSION)
    if hasattr(document["version"], "isoformat"):  # unquoted in YAML: a date
        document["version"] = document["version"].isoformat()
    return document

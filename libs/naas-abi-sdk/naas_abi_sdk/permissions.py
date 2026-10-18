"""A module's permission manifest: what it asks an admin to approve (RFC §8.3).

The manifest is a policy document (``version`` and ``statements`` of
``effect``, ``actions`` and ``resources``). A module declares it as
``BaseModule.permissions``, or in ``permissions.yaml`` beside the module's
code; otherwise it defaults from ``ModuleDependencies``:

* ``document``: everything on the module's own namespace, ``${module.id}``;
* ``secret``: the secrets named ``<module id>/...``; never every secret;
* ``dataset``: the namespace ``default`` the SDK's facade writes to, and the
  catalog, without unchecked SQL (``dataset:QueryUnchecked`` is denied);
* any other service it declares: every action of that service;
* the modules it depends on: their agents, models and apps, and the runs it
  starts;
* its own jobs, when it declares some, each by name: the broker gives the
  module the consumers of the jobs its manifest names, and only those.

``${module.id}`` and ``${module.project}`` are bound when the manifest is
approved. Bus topics have no default: a module using the bus declares them,
``bus:*`` on ``abi:-:-:bus:topic/<topic>``.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from naas_abi_sdk.module import BaseModule, ModuleDependencies

POLICY_VERSION = "2026-10-13"
MANIFEST_FILE = "permissions.yaml"
_ALIASES = {"kv": "keyvalue", "events": "event"}
_OWN_NAMESPACES = {
    "document": (
        "abi:-:-:document:namespace/${module.id}",
        "abi:-:-:document:collection/${module.id}/*",
        "abi:-:-:document:document/${module.id}/*",
    ),
    "secret": ("abi:-:-:secret:secret/${module.id}%2F*",),
    # The SDK's dataset facade writes to the namespace "default" (a dataset
    # namespace is an identifier, ^[A-Za-z][A-Za-z0-9_]*$, which a module id
    # need not be): granted until the SDK maps a module to a namespace of its own.
    "dataset": (
        "abi:-:-:dataset:namespace/default",
        "abi:-:-:dataset:dataset/default/*",
        "abi:-:-:dataset:catalog/-",
    ),
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
        resources = _OWN_NAMESPACES.get(service, (f"abi:*:*:{service}:*",))
        statements.append(
            _statement(f"Use{_sid(service)}", [f"{service}:*"], list(resources))
        )
        if service == "dataset":
            # SQL the query check cannot vouch for reads the engine host's files:
            # an admin action, never part of ``dataset:*`` for a module.
            statements.append(
                {
                    "sid": "NoUncheckedSql",
                    "effect": "Deny",
                    "actions": ["dataset:QueryUnchecked"],
                    "resources": ["abi:*:*:dataset:*"],
                }
            )
    if dependencies.modules:
        project = "${module.project}"
        reach = []
        for module_id in dependencies.modules:
            reach += [
                f"abi:-:-:discovery:module/{project}/{module_id}",
                f"abi:-:-:discovery:agent/{project}/{module_id}/*",
                f"abi:-:-:discovery:model/{project}/{module_id}/*",
                f"abi:-:-:discovery:app/{project}/{module_id}/*",
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
        statements.append(
            _statement(
                "FollowOwnRuns",
                ["discovery:GetAgentRun", "discovery:CancelAgentRun"],
                # Its own runs, and those of the user it acts for: a run started
                # for a user is that user's (RFC §6.4).
                [
                    "abi:-:-:discovery:run/${principal.id}/*",
                    "abi:-:-:discovery:run/${user.id}/*",
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
                        f"abi:-:-:discovery:job/${{module.project}}/${{module.id}}/{name}"
                        for name in names
                    ),
                    "abi:-:-:discovery:job_run/${module.project}/${module.id}/*",
                ],
            )
        )
    return {"version": POLICY_VERSION, "statements": statements}


def module_manifest(module_type: type[BaseModule]) -> dict[str, Any]:
    """The manifest ``module_type`` submits for approval."""
    declared = getattr(module_type, "permissions", None)
    if declared is not None:
        return _document(declared, f"{module_type.__name__}.permissions")
    found = _manifest_file(module_type)
    if found is not None:
        return _document(_load_yaml(found), str(found))
    jobs = [job.name for job in getattr(module_type, "jobs", ())]  # @job included
    return default_manifest(module_type.get_dependencies(), jobs=jobs)


def _manifest_file(module_type: type) -> Path | None:
    try:
        source = inspect.getfile(module_type)
    except (TypeError, OSError):
        return None
    candidate = Path(source).resolve().parent / MANIFEST_FILE
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

"""Remote modules as service accounts, and their permission manifests.

* A module runs as the service account ``module/<project>/<module_id>``.
* Its manifest is a policy document. ``${module.id}`` and ``${module.project}``
  are bound when it is approved; the approved document becomes the managed
  policy ``module.<project>.<module_id>``, attached to the account.
* Until then the account holds ``builtin.module_bootstrap`` only, which it
  keeps: its own discovery record and its own manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from naas_abi_core.services.iam.names import encode_segment
from naas_abi_core.services.iam.policy import (
    MODULE_VARIABLES,
    PolicyDocument,
    bind_variables,
)

# A project and a module id: one NATS subject token for the project (no dot),
# the module id as modules declare it (``acme.people``).
_PROJECT = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MODULE_ID = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_ACCOUNT = re.compile(r"^module/([^/]+)/([^/]+)$")


def check_module(project: str, module_id: str) -> None:
    if not _PROJECT.match(project or ""):
        raise ValueError(f"Invalid discovery project {project!r}")
    if not _MODULE_ID.match(module_id or ""):
        raise ValueError(f"Invalid module id {module_id!r}")


def account_name(project: str, module_id: str) -> str:
    check_module(project, module_id)
    return f"module/{project}/{module_id}"


def parse_account(name: str | None) -> tuple[str, str] | None:
    """``(project, module_id)`` of a module's service-account name, else None."""
    found = _ACCOUNT.match(name or "")
    if found is None:
        return None
    project, module_id = found.groups()
    if not _PROJECT.match(project) or not _MODULE_ID.match(module_id):
        return None
    return project, module_id


def subject_token(principal_id: str) -> str:
    """A principal as one NATS subject token, for hosting subjects:
    an ``sa_`` id's ULID part; anything else (test identities) hashed."""
    kind, _, rest = principal_id.partition("_")
    if kind == "sa" and rest.isalnum() and len(rest) == 26:
        return rest
    return hashlib.sha256(principal_id.encode()).hexdigest()[:26]


def policy_id(project: str, module_id: str) -> str:
    return f"module.{project}.{module_id}"


def variables(name: str | None) -> dict[str, str | None]:
    """The module variables for the principal named ``name`` (None: unresolved)."""
    parsed = parse_account(name)
    if parsed is None:
        return dict.fromkeys(MODULE_VARIABLES)
    project, module_id = parsed
    return {
        "module.project": encode_segment(project),
        "module.id": encode_segment(module_id),
    }


def manifest_sha256(document: Mapping[str, Any]) -> str:
    """The version of a manifest: SHA-256 of its canonical JSON."""
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def bind(document: PolicyDocument, project: str, module_id: str) -> PolicyDocument:
    """``document`` with ``${module.*}`` replaced: what an approval stores."""
    values = variables(account_name(project, module_id))
    statements = []
    for statement in document.statements:
        bound = bind_variables(statement, values)
        if bound is not None:
            statements.append(bound)
    return PolicyDocument(statements=tuple(statements), version=document.version)


# Placements an approval records: the module's own namespaces, on
# the platform, so no workspace can claim a name inside them.
NAMESPACE_SERVICES = ("document", "dataset")


def namespace_placements(module_id: str) -> list[tuple[str, str]]:
    namespace = encode_segment(module_id)
    return [
        (service, key)
        for service in NAMESPACE_SERVICES
        for key in (namespace, f"{namespace}/*")
    ]

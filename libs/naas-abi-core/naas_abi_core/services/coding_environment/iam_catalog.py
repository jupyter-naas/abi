"""The ``coding_environment`` action catalog.

An environment is personal: ``environment/<owner principal id>/<id>``, placed
in the call's target workspace when it is provisioned. The owner and the user
come from the call and the service's own records, never ``request.user_id``.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType

SERVICE = "coding_environment"
SUBJECT_PREFIX = "abi.svc.coding_environment.v1"


def _action(
    name: str,
    level: str,
    types: tuple[str, ...],
    *subjects: str,
    creates: bool = False,
    description: str = "",
) -> ActionSpec:
    return ActionSpec(
        name=name,
        level=level,  # type: ignore[arg-type]
        resource_types=types,
        creates=creates,
        subjects=tuple(
            s if s.startswith("abi.") else f"{SUBJECT_PREFIX}.{s}" for s in subjects
        ),
        description=description,
    )


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType(
            "environment",
            id="path",
            placement="placed",
            personal=True,
            description="environment/<owner principal id>/<environment id>.",
        ),
        ResourceType("template", id="opaque", placement="platform"),
        ResourceType(
            "coder_user",
            id="opaque",
            placement="platform",
            personal=True,
            description="The orchestrator account of a principal.",
        ),
    ),
    actions=(
        _action("ListTemplates", "list", ("template",), "list_templates"),
        _action("ListEnvironments", "list", ("environment",), "list_environments"),
        _action(
            "ListAllEnvironments", "admin", ("environment",), "list_all_environments"
        ),
        _action("GetStatus", "read", ("environment",), "get_status"),
        _action("GetLogs", "read", ("environment",), "get_logs"),
        _action("GetAccess", "write", ("environment",), "get_access"),
        _action("Provision", "write", ("environment",), "provision", creates=True),
        _action("Start", "write", ("environment",), "start"),
        _action("Stop", "write", ("environment",), "stop"),
        _action("Delete", "write", ("environment",), "delete"),
        _action("EnsureUser", "admin", ("coder_user",), "ensure_user"),
    ),
)

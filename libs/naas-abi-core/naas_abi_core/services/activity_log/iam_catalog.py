"""The ``activity_log`` action catalog (RFC §6.4, "activity_log").

An actor's log is a personal resource: ``actor/<principal id>``. The actor of a
recorded event is the call's user (or, for no user, the calling service
account), never a request field. Every user reads their own log through
``builtin.self``.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType

SERVICE = "activity_log"
SUBJECT_PREFIX = "abi.svc.activity_log.v1"

# A streamed query's transfer subjects (docs/adr/20261003_nats-streamed-results.md).
STREAM = tuple(
    f"{SUBJECT_PREFIX}.transfer.{operation}"
    for operation in ("open", "*.write", "*.start", "*.read", "*.close")
)


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
            "actor",
            id="opaque",
            placement="platform",
            personal=True,
            description="An actor's activity: actor/<principal id>.",
        ),
        ResourceType("service", id="singleton", placement="platform"),
    ),
    actions=(
        _action("ListActors", "list", ("actor",), "list_actors"),
        _action("Query", "read", ("actor",), "query"),
        _action("QueryStream", "read", ("actor",), *STREAM),
        _action("Record", "write", ("actor",), "record"),
        _action("Shutdown", "admin", ("service",), "shutdown"),
    ),
)

"""The ``event`` action catalog (RFC §6.4, "event").

Event types are placed by prefix (``iam:PutPlacement``); an unplaced type is
platform-level. A query with no type is filtered per event type (§6.3).
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType

SERVICE = "event"
SUBJECT_PREFIX = "abi.svc.event.v1"

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
            "event_type",
            id="opaque",
            placement="placed",
            description="An event type, by class IRI.",
        ),
        ResourceType(
            "cursor",
            id="path",
            placement="placed",
            description="cursor/<consumer>/<event type>: a consumer's position.",
        ),
    ),
    actions=(
        _action("ListEventTypes", "list", ("event_type",), "list_event_types"),
        _action("Query", "read", ("event_type",), "query"),
        _action("QueryStream", "read", ("event_type",), *STREAM),
        _action("MaxSeq", "read", ("event_type",), "max_seq"),
        _action(
            "QueryForConsumer",
            "read",
            ("event_type", "cursor"),
            "query_for_consumer",
        ),
        _action("GetCursor", "read", ("cursor",), "get_cursor"),
        _action("Append", "write", ("event_type",), "append"),
        _action("SetCursor", "write", ("cursor",), "set_cursor"),
    ),
)

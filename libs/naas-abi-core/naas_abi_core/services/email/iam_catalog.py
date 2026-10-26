"""The ``email`` action catalog.

Mail is sent from a sender (``sender/<from address>``, platform-level); a kept
copy is a message placed in the call's target workspace when it is sent.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType

SERVICE = "email"
SUBJECT_PREFIX = "abi.svc.email.v1"


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


# The sender a send with no from address is checked on.
DEFAULT_SENDER = "default"

CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType(
            "sender",
            id="opaque",
            placement="platform",
            description="A from address, or `default`.",
        ),
        ResourceType(
            "message",
            id="opaque",
            placement="placed",
            description="A kept copy of a sent message, by its id.",
        ),
    ),
    actions=(
        _action("ListSent", "list", ("message",), "list_sent"),
        _action("GetSent", "read", ("message",), "get_sent"),
        _action("Send", "write", ("sender", "message"), "send", creates=True),
        _action("DeleteSent", "write", ("message",), "delete_sent"),
    ),
)

"""The ``model_registry`` action catalog (RFC §6.4, "model_registry").

Every model is platform-level, by canonical model id. Chatting with a model,
streamed or not, and embedding are read actions.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType

SERVICE = "model_registry"
SUBJECT_PREFIX = "abi.svc.model_registry.v1"

# A large chat, stream or embedding call goes through a transfer session
# (docs/adr/20261003_nats-streamed-results.md); the operation it opens is
# checked by the registry like the direct call.
TRANSFER = tuple(
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
            "model",
            id="opaque",
            placement="platform",
            description="A model, by canonical model id.",
        ),
    ),
    actions=(
        _action("ListModels", "list", ("model",), "list_models"),
        _action("Resolve", "read", ("model",), "resolve"),
        _action("Chat", "read", ("model",), "chat", *TRANSFER),
        _action(
            "ChatStream",
            "read",
            ("model",),
            "stream_open",
            "*.stream_next",
            "*.stream_close",
            *TRANSFER,
        ),
        _action("Embed", "read", ("model",), "embed", *TRANSFER),
    ),
)

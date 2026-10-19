"""cache's action catalog (RFC §6.4, "cache").

One ``key/<key>`` per cache key, opaque, placed by prefix; ``service/-`` for
the service itself. The per-tier subjects are the engine's own.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ResourceType,
    service_action,
)

SERVICE = "cache"
SUBJECT_PREFIX = "abi.svc.cache.v1"
KEY = "key"
SERVICE_TYPE = "service"


def _subjects(name: str, *, tiered: bool = True) -> tuple[str, ...]:
    own = (f"{SUBJECT_PREFIX}.{name}",)
    return own + ((f"{SUBJECT_PREFIX}.tier.*.{name}",) if tiered else ())


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType(KEY, id="opaque", description="A cache key."),
        ResourceType(
            SERVICE_TYPE,
            id="singleton",
            placement="platform",
            description="The cache service itself.",
        ),
    ),
    actions=(
        service_action("ListKeys", "list", (KEY,), *_subjects("list_keys")),
        service_action("Get", "read", (KEY,), *_subjects("get")),
        service_action("Exists", "read", (KEY,), *_subjects("exists")),
        service_action("Set", "write", (KEY,), *_subjects("set")),
        service_action("SetIfAbsent", "write", (KEY,), *_subjects("set_if_absent")),
        service_action("Delete", "write", (KEY,), *_subjects("delete")),
        service_action(
            "Describe", "admin", (SERVICE_TYPE,), *_subjects("describe", tiered=False)
        ),
    ),
)

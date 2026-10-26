"""keyvalue's action catalog: one ``key/<key>`` per key,
opaque, placed by key prefix."""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ResourceType,
    service_action,
)

SERVICE = "keyvalue"
SUBJECT_PREFIX = "abi.svc.keyvalue.v1"
KEY = "key"


def _subject(name: str) -> str:
    return f"{SUBJECT_PREFIX}.{name}"


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(ResourceType(KEY, id="opaque", description="A key."),),
    actions=(
        service_action("ListKeys", "list", (KEY,), _subject("list_keys")),
        service_action("Get", "read", (KEY,), _subject("get")),
        service_action("Exists", "read", (KEY,), _subject("exists")),
        service_action("GetTtl", "read", (KEY,), _subject("get_ttl")),
        service_action("Set", "write", (KEY,), _subject("set")),
        service_action(
            "SetIfNotExists", "write", (KEY,), _subject("set_if_not_exists")
        ),
        service_action("Delete", "write", (KEY,), _subject("delete")),
        service_action(
            "DeleteIfValueMatches",
            "write",
            (KEY,),
            _subject("delete_if_value_matches"),
        ),
    ),
)

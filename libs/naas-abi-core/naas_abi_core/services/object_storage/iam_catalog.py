"""object_storage's action catalog (RFC §6.4, "object_storage").

An object is ``object/<path>``: the prefix and the key joined with one ``/``
(leading and trailing ``/`` stripped from the prefix), each part encoded on
its own. Nexus places its ``workspaces/<ws>/*`` and ``users/<user>/*`` prefixes.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ResourceType,
    service_action,
    stream_subjects,
)
from naas_abi_core.services.iam.names import path_parts

SERVICE = "object_storage"
SUBJECT_PREFIX = "abi.svc.object_storage.v1"
STREAM = stream_subjects(f"{SUBJECT_PREFIX}.transfer")
OBJECT = "object"


def _subject(name: str) -> str:
    return f"{SUBJECT_PREFIX}.{name}"


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType(
            OBJECT,
            id="path",
            description="An object, by its prefix and key joined with '/'.",
        ),
    ),
    actions=(
        service_action("ListObjects", "list", (OBJECT,), _subject("list_objects")),
        service_action(
            "ListObjectsRecursive",
            "list",
            (OBJECT,),
            _subject("list_objects_recursive"),
        ),
        service_action("GetObject", "read", (OBJECT,), _subject("get_object")),
        service_action(
            "GetObjectMetadata", "read", (OBJECT,), _subject("get_object_metadata")
        ),
        service_action("GetObjectStream", "read", (OBJECT,), *STREAM),
        service_action("PutObject", "write", (OBJECT,), _subject("put_object")),
        service_action("PutObjectStream", "write", (OBJECT,), *STREAM),
        service_action("DeleteObject", "write", (OBJECT,), _subject("delete_object")),
    ),
)


def object_parts(prefix: str, key: str = "") -> list[str]:
    """The path id parts of ``prefix`` joined with ``key`` (RFC §4.3)."""
    stripped = prefix.strip("/")
    if not key:
        return path_parts(stripped)
    return path_parts(f"{stripped}/{key}" if stripped else key)

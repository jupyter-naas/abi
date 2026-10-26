"""dataset's action catalog.

``namespace/<ns>`` is a placed container holding ``dataset/<ns>/<name>``;
``catalog/-`` is the platform-level catalog of snapshots.

``QueryUnchecked`` on ``catalog/-`` runs SQL the query check cannot vouch for:
catalog maintenance (``DESCRIBE``, ``ALTER``, ``CALL ducklake_*``) and, with it,
DuckDB's file-reading functions on the engine host. It is the engine's own;
``builtin.api`` denies it.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ResourceType,
    service_action,
    stream_subjects,
)

SERVICE = "dataset"
SUBJECT_PREFIX = "abi.svc.dataset.v1"
STREAM = stream_subjects(f"{SUBJECT_PREFIX}.transfer")
NAMESPACE = "namespace"
DATASET = "dataset"
CATALOG_TYPE = "catalog"


def _subject(name: str) -> str:
    return f"{SUBJECT_PREFIX}.{name}"


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType(NAMESPACE, id="path", container=True, description="A namespace."),
        ResourceType(DATASET, id="path", description="A dataset, in its namespace."),
        ResourceType(
            CATALOG_TYPE,
            id="singleton",
            placement="platform",
            description="The catalog of snapshots.",
        ),
    ),
    actions=(
        service_action("List", "list", (DATASET,), _subject("list")),
        service_action(
            "ListSnapshots", "list", (CATALOG_TYPE,), _subject("list_snapshots")
        ),
        service_action("Describe", "read", (DATASET,), _subject("describe")),
        service_action(
            "NamespaceVersion", "read", (NAMESPACE,), _subject("namespace_version")
        ),
        service_action("Query", "read", (DATASET,), _subject("query")),
        service_action("QueryStream", "read", (DATASET,), *STREAM),
        service_action(
            "QueryUnchecked",
            "admin",
            (CATALOG_TYPE,),
            _subject("query"),
            *STREAM,
        ),
        service_action("Create", "write", (DATASET,), _subject("create"), creates=True),
        service_action("Write", "write", (DATASET,), _subject("write")),
        service_action("WriteStream", "write", (DATASET,), *STREAM),
        service_action(
            "InlinedRowCount", "admin", (DATASET,), _subject("inlined_row_count")
        ),
        service_action("Flush", "admin", (DATASET,), _subject("flush")),
        service_action("Compact", "admin", (DATASET,), _subject("compact")),
        service_action("Drop", "admin", (DATASET,), _subject("drop")),
    ),
)

"""document's action catalog.

``namespace/<ns>`` and ``collection/<ns>/<c>`` are placed containers holding
``document/<ns>/<c>/<id>``. Namespace administration is ``Namespaces``,
``EnsureCollection`` and ``DropCollection``, granted by policy like any other
action: no identity holds it implicitly. The built-in IdP's namespace is
sealed to it (``SEALS``): not even ``api`` or ``engine`` reach it.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ResourceType,
    service_action,
)
from naas_abi_core.services.iam.IAMPorts import Seal
from naas_abi_core.services.iam.names import anywhere

SERVICE = "document"
SUBJECT_PREFIX = "abi.svc.document.v1"
NAMESPACE = "namespace"
COLLECTION = "collection"
DOCUMENT = "document"


def _subject(name: str) -> str:
    return f"{SUBJECT_PREFIX}.{name}"


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType(NAMESPACE, id="path", id_prefix=True, description="A namespace."),
        ResourceType(
            COLLECTION,
            id="path",
            id_prefix=True,
            description="A collection, in its namespace.",
        ),
        ResourceType(DOCUMENT, id="path", description="A document, in its collection."),
    ),
    actions=(
        service_action("Namespaces", "list", (NAMESPACE,), _subject("namespaces")),
        service_action("Collections", "list", (COLLECTION,), _subject("collections")),
        service_action(
            "CollectionSpec", "read", (COLLECTION,), _subject("collection_spec")
        ),
        service_action(
            "EnsureCollection",
            "admin",
            (COLLECTION,),
            _subject("ensure_collection"),
            creates=True,
        ),
        service_action(
            "DropCollection", "admin", (COLLECTION,), _subject("drop_collection")
        ),
        service_action("Get", "read", (DOCUMENT,), _subject("get")),
        service_action("Find", "read", (COLLECTION,), _subject("find")),
        service_action("Count", "read", (COLLECTION,), _subject("count")),
        service_action("Put", "write", (DOCUMENT,), _subject("put")),
        service_action("Delete", "write", (DOCUMENT,), _subject("delete")),
    ),
)

# Sealed to the built-in IdP, wherever a placement puts it.
IDP_NAMESPACE = "idp"
SEALS: tuple[Seal, ...] = (
    # Sealed at any placement: the platform's and every container's.
    *(
        Seal(pattern, "idp", module_id="idp")
        for rest in (
            f"document:namespace/{IDP_NAMESPACE}",
            f"document:collection/{IDP_NAMESPACE}/*",
            f"document:document/{IDP_NAMESPACE}/*",
        )
        for pattern in anywhere(rest)
    ),
)

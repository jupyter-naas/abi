"""document's action catalog (RFC §6.4, "document").

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
        ResourceType(NAMESPACE, id="path", container=True, description="A namespace."),
        ResourceType(
            COLLECTION,
            id="path",
            container=True,
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

# Sealed to the built-in IdP (RFC §11.3, §12.3), wherever a placement puts it.
IDP_NAMESPACE = "idp"
SEALS: tuple[Seal, ...] = (
    Seal(f"abi:*:*:document:namespace/{IDP_NAMESPACE}", "idp"),
    Seal(f"abi:*:*:document:collection/{IDP_NAMESPACE}/*", "idp"),
    Seal(f"abi:*:*:document:document/{IDP_NAMESPACE}/*", "idp"),
)

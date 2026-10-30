"""vector_store's action catalog.

``collection/<name>`` is a placed container; its vectors are
``vector/<collection>/<id>``. ``service/-`` is the service itself.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ResourceType,
    service_action,
    stream_subjects,
)

SERVICE = "vector_store"
SUBJECT_PREFIX = "abi.svc.vector_store.v1"
STREAM = stream_subjects(f"{SUBJECT_PREFIX}.transfer")
COLLECTION = "collection"
VECTOR = "vector"
SERVICE_TYPE = "service"


def _subject(name: str) -> str:
    return f"{SUBJECT_PREFIX}.{name}"


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType(
            COLLECTION, id="path", id_prefix=True, description="A collection."
        ),
        ResourceType(VECTOR, id="path", description="A vector, in its collection."),
        ResourceType(
            SERVICE_TYPE,
            id="singleton",
            placement="platform",
            description="The vector store service itself.",
        ),
    ),
    actions=(
        service_action(
            "ListCollections", "list", (COLLECTION,), _subject("list_collections")
        ),
        service_action(
            "GetCollectionInfo", "read", (COLLECTION,), _subject("get_collection_info")
        ),
        service_action(
            "CreateCollection",
            "write",
            (COLLECTION,),
            _subject("create_collection"),
            creates=True,
        ),
        service_action(
            "DeleteCollection", "admin", (COLLECTION,), _subject("delete_collection")
        ),
        service_action("ListVectors", "list", (VECTOR,), _subject("list_vectors")),
        service_action("ListVectorsStream", "list", (VECTOR,), *STREAM),
        service_action("Search", "read", (COLLECTION,), _subject("search")),
        service_action(
            "CountVectors", "read", (COLLECTION,), _subject("count_vectors")
        ),
        service_action("GetVector", "read", (VECTOR,), _subject("get_vector")),
        service_action("StoreVectors", "write", (VECTOR,), _subject("store_vectors")),
        service_action("UpdateVector", "write", (VECTOR,), _subject("update_vector")),
        service_action("DeleteVectors", "write", (VECTOR,), _subject("delete_vectors")),
        service_action("Initialize", "admin", (SERVICE_TYPE,), _subject("initialize")),
        service_action("Close", "admin", (SERVICE_TYPE,), _subject("close")),
    ),
)

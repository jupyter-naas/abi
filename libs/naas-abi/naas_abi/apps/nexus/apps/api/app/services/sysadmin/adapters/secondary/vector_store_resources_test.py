import asyncio
import json

import numpy as np
import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.vector_store_resources import (
    VectorStoreResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
    ResourceTooLarge,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)
from naas_abi_core.services.vector_store.adapters.SqliteVecAdapter import SqliteVecAdapter
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

COLLECTION = "seeded"
DIMENSION = 3


def _document(text: str) -> dict:
    return {
        "vector": [0.1, 0.2, 0.3],
        "metadata": {"text": text},
        "payload": {"value": text},
    }


def _seed(service: VectorStoreService) -> VectorStoreService:
    service.ensure_collection(COLLECTION, DIMENSION)
    for name, value in fixtures.SEED_ITEMS.items():
        document = _document(value.decode())
        service.add_documents(
            COLLECTION,
            [name],
            [np.array(document["vector"], dtype=np.float32)],
            metadata=[document["metadata"]],
            payloads=[document["payload"]],
        )
    service.ensure_collection("other", 2, distance_metric="euclidean")
    return service


def _qdrant() -> VectorStoreService:
    return _seed(VectorStoreService(QdrantInMemoryAdapter(storage_path=":memory:")))


class _Contract(ServiceResourcesContract):
    base = COLLECTION
    sized = False

    def encode(self, text: str) -> bytes:
        return json.dumps(_document(text)).encode()

    def assert_shown(self, shown: str | None, text: str) -> None:
        assert shown is not None and text in shown

    def assert_downloaded(self, data: bytes, text: str) -> None:
        assert text in json.loads(data)["payload"]["value"]


class TestVectorStoreResourcesOnQdrant(_Contract):
    @pytest.fixture
    def resources(self):
        return VectorStoreResources(_qdrant())


class TestVectorStoreResourcesOnSqliteVec(_Contract):
    @pytest.fixture
    def resources(self, tmp_path):
        pytest.importorskip("sqlite_vec")
        return VectorStoreResources(
            _seed(VectorStoreService(SqliteVecAdapter(str(tmp_path / "vectors.db"))))
        )


@pytest.fixture
def resources():
    return VectorStoreResources(_qdrant())


def run(coro):
    return asyncio.run(coro)


def test_root_lists_collections_with_their_shape(resources):
    page = run(resources.list(""))

    assert [(e.id, e.kind) for e in page.entries] == [
        ("other", "container"),
        ("seeded", "container"),
    ]
    seeded = page.entries[1]
    assert seeded.actions == ("delete",)
    assert {k: seeded.attributes[k] for k in ("documents", "dimension", "distance")} == {
        "documents": "3",
        "dimension": "3",
        "distance": "cosine",
    }


def test_reading_a_document_shows_its_shape_not_the_whole_vector(resources):
    detail = run(resources.read("seeded/alpha"))
    body = json.loads(detail.content.text)

    assert body["id"] == "alpha"
    assert body["collection"] == "seeded"
    assert body["dimension"] == 3
    assert body["vector_head"] == pytest.approx([0.1, 0.2, 0.3])
    assert body["metadata"] == {"text": "first value"}
    assert body["payload"] == {"value": "first value"}


def test_download_carries_the_full_vector(resources):
    body = json.loads(run(resources.download("seeded/alpha", max_bytes=1 << 20)))

    assert body["vector"] == pytest.approx([0.1, 0.2, 0.3])
    with pytest.raises(ResourceTooLarge):
        run(resources.download("seeded/alpha", max_bytes=10))


def test_writing_into_a_new_collection_creates_it_from_the_vector(resources):
    entry = run(resources.write("fresh/doc-1", json.dumps({"vector": [1, 0, 0, 0]}).encode()))

    assert (entry.id, entry.kind) == ("fresh/doc-1", "item")
    fresh = run(resources.stat("fresh"))
    assert fresh.kind == "container"
    assert {k: fresh.attributes[k] for k in ("documents", "dimension", "distance")} == {
        "documents": "1",
        "dimension": "4",
        "distance": "cosine",
    }


def test_replacing_without_a_vector_keeps_the_stored_one(resources):
    run(resources.write("seeded/alpha", json.dumps({"payload": {"value": "edited"}}).encode()))

    body = json.loads(run(resources.download("seeded/alpha", max_bytes=1 << 20)))
    assert body["vector"] == pytest.approx([0.1, 0.2, 0.3])
    assert body["payload"] == {"value": "edited"}
    assert body["metadata"] == {}


@pytest.mark.parametrize(
    "resource_id,content",
    [
        ("seeded", b'{"vector": [1, 2, 3]}'),  # a collection, not a document
        ("seeded/new", b"not json"),
        ("seeded/new", b"[1, 2, 3]"),
        ("seeded/new", b'{"metadata": {}}'),  # creating needs a vector
        ("seeded/new", b'{"vector": [1, 2]}'),  # wrong dimension
        ("seeded/new", b'{"vector": ["a", "b", "c"]}'),
        ("seeded/new", b'{"vector": [1, 2, 3], "payload": "text"}'),
        ("/new", b'{"vector": [1, 2, 3]}'),
        ("seeded/", b'{"vector": [1, 2, 3]}'),
    ],
)
def test_invalid_writes_are_rejected(resources, resource_id, content):
    with pytest.raises(InvalidResource):
        run(resources.write(resource_id, content))
    assert "new" not in {e.name for e in run(resources.list("seeded")).entries}


def test_deleting_a_collection_removes_its_documents(resources):
    run(resources.delete("seeded"))

    assert [e.id for e in run(resources.list("")).entries] == ["other"]
    with pytest.raises(ResourceNotFound):
        run(resources.stat("seeded/alpha"))
    with pytest.raises(ResourceNotFound):
        run(resources.list("seeded"))


def test_unknown_collections_are_not_found(resources):
    for call in (resources.list("nope"), resources.stat("nope"), resources.stat("nope/x")):
        with pytest.raises(ResourceNotFound):
            run(call)


def test_collections_summarize_their_shape_and_carry_a_sample_vector(resources):
    collections = {e.name: e for e in run(resources.list("")).entries}

    seeded = collections[COLLECTION].attributes
    assert seeded["summary"] == "3 vectors · 3-d · cosine"
    assert [float(v) for v in seeded["sample"].split(",")] == pytest.approx([0.1, 0.2, 0.3])
    assert "sample" not in collections["other"].attributes
    assert collections["other"].attributes["summary"].startswith("0 vectors · 2-d")


def test_documents_are_summarized_from_their_text_fields_first(resources):
    service = resources._vectors
    service.add_documents(
        COLLECTION,
        ["chunk-1"],
        [np.array([0.3, 0.2, 0.1], dtype=np.float32)],
        metadata=[{"source": "handbook.pdf", "page": 4}],
        payloads=[{"text": "Paris   is the\ncapital of France.", "n": 1}],
    )

    entries = {e.name: e for e in run(resources.list(COLLECTION)).entries}

    assert entries["chunk-1"].attributes["summary"] == "Paris is the capital of France."
    assert entries["chunk-1"].attributes["fields"] == "n, page, source, text"
    assert entries["alpha"].attributes["summary"] == "first value"


def test_reading_a_vector_carries_a_vector_view(resources):
    detail = run(resources.read(f"{COLLECTION}/alpha"))

    view = detail.view
    assert view["type"] == "vector"
    assert view["dimension"] == DIMENSION
    assert view["components"] == pytest.approx([0.1, 0.2, 0.3])
    assert view["norm"] == pytest.approx(float(np.linalg.norm([0.1, 0.2, 0.3])), rel=1e-5)
    assert view["payload"] == {"value": "first value"}
    assert view["metadata"] == {"text": "first value"}
    json.dumps(view)

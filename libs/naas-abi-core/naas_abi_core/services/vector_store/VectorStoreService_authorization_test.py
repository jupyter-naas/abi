"""The vector store passes the authorization contract."""

from __future__ import annotations

import numpy as np
import pytest

from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.iam.tests.data_service_contract import (
    ANY_OK,
    DENY,
    HIDDEN,
    NOT_FOUND,
    SECRET,
    Case,
    DataServiceContract,
    ok,
)
from naas_abi_core.services.vector_store.adapters.primary.vector_store__primary_adapter__NATS import (
    VectorStorePrimaryAdapterNATS,
)
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)
from naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient import (
    VectorStoreSecondaryAdapterNATSClient,
)
from naas_abi_core.services.vector_store.iam_catalog import CATALOG
from naas_abi_core.services.vector_store.IVectorStorePort import (
    CollectionNotFoundError,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

VECTOR = np.array([1.0, 0.0, 0.0])


def _ids(documents) -> list[str]:
    return sorted(document.id for document in documents)


def _streamed(store, collection):
    with store.list_documents_stream(collection) as documents:
        return _ids(documents)


class TestVectorStoreAuthorization(DataServiceContract):
    catalog = CATALOG

    def build_owner(self, tmp_path):
        return VectorStoreService(QdrantInMemoryAdapter())

    def seed(self, owner):
        for collection in ("shared", "private", "frozen"):
            owner.ensure_collection(collection, 3)
            owner.add_documents(collection, [f"{collection}-1"], [VECTOR])
        owner.add_documents("shared", ["shared-2"], [VECTOR])

    def build_primary(self, owner):
        return VectorStorePrimaryAdapterNATS(owner, SECRET)

    def build_remote(self, url, identity):
        return VectorStoreService(
            VectorStoreSecondaryAdapterNATSClient(url, TEST_TOKENS.source(identity))
        )

    def close_remote(self, remote):
        remote.adapter.close()

    def granted_resources(self):
        return [
            "abi:-:-:vector_store:collection/shared",
            "abi:-:-:vector_store:vector/shared/*",
        ]

    def denied_resources(self):
        return [
            "abi:-:-:vector_store:collection/private",
            "abi:-:-:vector_store:vector/private/*",
        ]

    def read_only_resources(self):
        return [
            "abi:-:-:vector_store:collection/frozen",
            "abi:-:-:vector_store:vector/frozen/*",
        ]

    def outcome_of(self, exc):
        return NOT_FOUND if isinstance(exc, CollectionNotFoundError) else None

    def cases(self):
        return [
            Case(
                "list collections",
                lambda v: v.list_collections(),
                nobody=ok([]),
                granted=ok(["shared"]),
                denied=ok(["frozen", "shared"]),
                view=sorted,
            ),
            Case(
                "describe a denied collection",
                lambda v: v.get_collection_info("private"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "search a granted collection",
                lambda v: v.search("shared", VECTOR, k=5),
                nobody=HIDDEN,
                granted=ok(["shared-1", "shared-2"]),
                denied=ok(["shared-1", "shared-2"]),
                view=lambda hits: sorted(hit.id for hit in hits),
            ),
            Case(
                "list a granted collection's vectors",
                lambda v: v.list_documents("shared"),
                nobody=HIDDEN,
                granted=ok(["shared-1", "shared-2"]),
                denied=ok(["shared-1", "shared-2"]),
                view=lambda page: _ids(page.documents),
            ),
            Case(
                "stream a granted collection's vectors",
                lambda v: _streamed(v, "shared"),
                nobody=HIDDEN,
                granted=ok(["shared-1", "shared-2"]),
                denied=ok(["shared-1", "shared-2"]),
            ),
            Case(
                "stream a denied collection's vectors",
                lambda v: _streamed(v, "private"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "get a denied vector",
                lambda v: v.get_document("private", "private-1"),
                nobody=ok(None),
                granted=ok(None),
                denied=ok(None),
            ),
            Case(
                "count a read-only collection",
                lambda v: v.get_collection_size("frozen"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=ok(1),
            ),
            Case(
                "store into a read-only collection",
                lambda v: v.add_documents("frozen", ["frozen-2"], [VECTOR]),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "delete a denied vector",
                lambda v: v.delete_documents("private", ["private-1"]),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "create a collection",
                lambda v: v.ensure_collection("fresh", 3),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=ANY_OK,
            ),
            Case(
                "drop a read-only collection",
                lambda v: v.delete_collection("frozen"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "store into a granted collection",
                lambda v: v.add_documents("shared", ["shared-3"], [VECTOR]),
                nobody=HIDDEN,
                granted=ANY_OK,
                denied=ANY_OK,
            ),
        ]


def test_recreating_a_collection_needs_delete_only_when_it_exists(tmp_path):
    from naas_abi_core.engine.call_context import use_call_context
    from naas_abi_core.services.iam.enforcement import internal_call
    from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
    from naas_abi_core.services.iam.tests.data_service_contract import caller
    from naas_abi_core.services.iam.tests.iam_harness import document, statement

    contract = TestVectorStoreAuthorization()
    owner, iam = contract._owner(tmp_path)
    with internal_call():
        iam.create_service_account("builder")
        policy = iam.create_policy(
            "create-only",
            document(
                statement(
                    "Allow",
                    [
                        "vector_store:CreateCollection",
                        "vector_store:ListCollections",
                    ],
                    ["*"],
                )
            ),
        )
        iam.attach_policy(policy.id, contract._id(iam, "builder"))
    with use_call_context(caller("builder")):
        owner.ensure_collection("brand-new", 3, recreate=True)
        with pytest.raises((PermissionDeniedError, CollectionNotFoundError)):
            owner.ensure_collection("shared", 3, recreate=True)
    with internal_call():
        assert "brand-new" in owner.list_collections()
        # The refused recreate dropped nothing.
        assert _ids(owner.list_documents("shared").documents) == [
            "shared-1",
            "shared-2",
        ]

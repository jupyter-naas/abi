"""Vector store JSON values, the vector page/info calls, and regenerated proxies."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.email.v1 import email_pb2 as email
from naas_abi_proto.vector_store.v1 import vector_store_pb2 as vectors
from naas_abi_proto.vector_store.values import decode_object, encode_object

from naas_abi_sdk.services import (
    CodingEnvironmentService,
    EmailService,
    SourceControlService,
    VectorStoreService,
)
from naas_abi_sdk.services.models import (
    CollectionInfo,
    SearchResult,
    SentEmail,
    SentEmailSummary,
    VectorDocument,
    VectorPage,
)

BIG = 2**60 + 1
METADATA = {"index": 3, "big": BIG, "nested": {"n": 42, "items": [1, 2.5]}}


def _document(id: str, **values) -> vectors.VectorDocument:
    return vectors.VectorDocument(
        id=id,
        metadata=encode_object(values.get("metadata", {})),
        payload=encode_object(values["payload"]) if "payload" in values else None,
    )


def test_metadata_payloads_and_filters_are_sent_as_exact_json():
    client = AsyncMock()
    client.list_collections.return_value = vectors.ListCollectionsResponse(
        collections=vectors.CollectionNames(names=["docs"])
    )
    client.search.return_value = vectors.SearchResponse(
        results=vectors.SearchResultList(results=[])
    )
    service = VectorStoreService(client)

    asyncio.run(
        service.add_documents(
            "docs", ["a", "b"], [[0.1], [0.2]], metadata=[METADATA, {}], payloads=None
        )
    )
    asyncio.run(service.search_similar("docs", [0.1], filter={"index": 3}))
    asyncio.run(service.update_document("docs", "a", metadata={"big": BIG}))

    stored = client.store_vectors.call_args.args[0].documents
    assert decode_object(stored[0].metadata) == METADATA
    assert not stored[0].HasField("payload")
    assert decode_object(client.search.call_args.args[0].filter) == {"index": 3}
    update = client.update_vector.call_args.args[0]
    assert decode_object(update.metadata) == {"big": BIG}
    assert not update.HasField("payload")


def test_documents_and_results_come_back_with_exact_types():
    client = AsyncMock()
    client.get_vector.return_value = vectors.GetVectorResponse(
        found=vectors.VectorDocumentOrNone(
            document=_document("a", metadata=METADATA, payload={"count": 7})
        )
    )
    client.search.return_value = vectors.SearchResponse(
        results=vectors.SearchResultList(
            results=[
                vectors.SearchResult(
                    id="a", score=0.5, metadata=encode_object(METADATA)
                )
            ]
        )
    )
    service = VectorStoreService(client)

    document = asyncio.run(service.get_document("docs", "a"))
    (result,) = asyncio.run(service.search_similar("docs", [0.1]))

    assert isinstance(document, VectorDocument)
    assert document.metadata == METADATA and document.payload == {"count": 7}
    assert type(document.metadata["nested"]["n"]) is int
    assert isinstance(result, SearchResult)
    assert result.metadata == METADATA and result.payload is None


def test_list_documents_pages_and_collection_info():
    client = AsyncMock()
    client.list_vectors.return_value = vectors.ListVectorsResponse(
        page=vectors.VectorPage(
            documents=[_document("a", metadata={"n": 1})], next_cursor="b"
        )
    )
    client.get_collection_info.return_value = vectors.GetCollectionInfoResponse(
        info=vectors.CollectionInfo(name="docs", dimension=3, size=2)
    )
    service = VectorStoreService(client)

    page = asyncio.run(service.list_documents("docs", limit=1, cursor="a"))
    info = asyncio.run(service.get_collection_info("docs"))

    assert isinstance(page, VectorPage) and page.next_cursor == "b"
    assert page.documents[0].metadata == {"n": 1}
    request = client.list_vectors.call_args.args[0]
    assert (request.limit, request.cursor, request.include_vectors) == (1, "a", False)
    assert isinstance(info, CollectionInfo)
    assert (info.name, info.dimension, info.distance_metric, info.size) == (
        "docs",
        3,
        None,
        2,
    )
    with pytest.raises(ValueError):
        asyncio.run(service.list_documents("docs", limit=0))


def test_sent_email_calls_return_their_dtos():
    summary = email.SentEmailSummary(
        message_id="m1", sent_at="2026-10-04T12:00:00Z", size=10, subject="Hi"
    )
    client = AsyncMock()
    client.list_sent.return_value = email.ListSentResponse(
        messages=email.SentEmailSummaries(messages=[summary])
    )
    client.get_sent.return_value = email.GetSentResponse(
        message=email.SentEmail(summary=summary, raw=b"From: a\r\n")
    )
    service = EmailService(client)

    (listed,) = asyncio.run(service.list_sent(limit=5))
    sent = asyncio.run(service.get_sent("m1"))

    assert isinstance(listed, SentEmailSummary) and listed.subject == "Hi"
    assert isinstance(sent, SentEmail) and sent.raw == b"From: a\r\n"
    assert sent.summary.message_id == "m1"


def test_regenerated_proxies_expose_the_newer_calls():
    assert callable(CodingEnvironmentService.list_all_environments)
    assert callable(SourceControlService.delete_repo)
    assert callable(EmailService.delete_sent)

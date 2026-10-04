"""Streamed vector listing through the SDK facade (transfer/v1 frames)."""

import asyncio
from types import SimpleNamespace

import pytest
from naas_abi_proto.vector_store.v1 import vector_store_pb2 as pb

from naas_abi_sdk.services import FACTORIES
from naas_abi_sdk.services.models import VectorDocument
from naas_abi_sdk.transport import RPCError


class StreamTransport:
    """The owner side of one transfer stream: a list of frames, read in order."""

    def __init__(self, frames, *, no_responders=False):
        self.frames, self.no_responders = list(frames), no_responders
        self.opened, self.closed, self.read = [], [], 0

    async def connect(self):
        return SimpleNamespace(max_payload=1024 * 1024)

    async def call(self, subject, request, response_type, transfer=None):
        operation = subject.rsplit(".", 1)[1]
        if operation == "open":
            if self.no_responders:
                from nats.errors import NoRespondersError

                raise NoRespondersError()
            self.opened.append((subject, request.operation, request.metadata))
            return response_type(id=f"{'a' * 32}:s", chunk_bytes=request.chunk_bytes)
        if operation == "start":
            return response_type()
        if operation == "close":
            self.closed.append(request.id)
            return response_type()
        if self.read >= len(self.frames):
            return response_type(done=True, sequence=request.sequence)
        self.read += 1
        return response_type(
            data=self.frames[self.read - 1], frame_end=True, sequence=request.sequence
        )


def _page(*numbers, with_vectors=True):
    return pb.VectorPage(
        documents=[
            pb.VectorDocument(
                id=f"doc_{n}",
                vector=pb.VectorData(values=[float(n), 0.5]) if with_vectors else None,
                metadata={"n": n},
                payload={"text": f"row {n}"},
            )
            for n in numbers
        ]
    ).SerializeToString()


def test_list_documents_stream_reads_documents_frame_by_frame():
    transport = StreamTransport([_page(1, 2), _page(3)])
    service = FACTORIES["vector_store"](SimpleNamespace(_transport=transport))

    async def scenario():
        async with service.list_documents_stream(
            "docs", include_vectors=True
        ) as documents:
            return [document async for document in documents]

    documents = asyncio.run(scenario())

    assert [d.id for d in documents] == ["doc_1", "doc_2", "doc_3"]
    assert all(isinstance(d, VectorDocument) for d in documents)
    assert documents[0].vector == [1.0, 0.5]
    assert documents[0].metadata == {"n": 1}
    assert documents[0].payload == {"text": "row 1"}
    ((subject, operation, metadata),) = transport.opened
    assert subject == "abi.svc.vector_store.v1.transfer.open"
    request = pb.ListVectorsRequest.FromString(metadata)
    assert (operation, request.collection_name, request.include_vectors) == (
        "list_vectors",
        "docs",
        True,
    )
    assert transport.closed == [f"{'a' * 32}:s"]


def test_list_documents_stream_without_vectors_and_leaving_early():
    transport = StreamTransport([_page(1, 2, with_vectors=False), _page(3)])
    service = FACTORIES["vector_store"](SimpleNamespace(_transport=transport))

    async def scenario():
        async with service.list_documents_stream("docs") as documents:
            return await anext(documents)

    first = asyncio.run(scenario())

    assert first.id == "doc_1" and first.vector is None
    assert transport.read == 1  # the second frame was never fetched
    assert transport.closed == [f"{'a' * 32}:s"]


def test_list_documents_stream_needs_a_streaming_engine():
    transport = StreamTransport([], no_responders=True)
    service = FACTORIES["vector_store"](SimpleNamespace(_transport=transport))

    async def scenario():
        async with service.list_documents_stream("docs") as documents:
            return [document async for document in documents]

    with pytest.raises(RPCError, match="UNAVAILABLE"):
        asyncio.run(scenario())

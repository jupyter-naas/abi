from naas_abi_core.proto.vector_store.v1 import vector_store_pb2
from naas_abi_core.services.vector_store.adapters.vector_store_stream_codec import (
    decode_frame,
    document_frames,
)
from naas_abi_proto.vector_store.values import decode_object, encode_object


def _document(n: int) -> vector_store_pb2.VectorDocument:
    return vector_store_pb2.VectorDocument(
        id=f"doc_{n}",
        vector=vector_store_pb2.VectorData(values=[float(n)] * 64),
        metadata=encode_object({"n": n}),
    )


def test_documents_cross_the_wire_in_bounded_frames_in_order():
    frames = list(document_frames((_document(n) for n in range(1_000)), 16_384))

    assert len(frames) > 1 and all(len(frame) < 2 * 16_384 for frame in frames)
    decoded = [document for frame in frames for document in decode_frame(frame)]
    assert [d.id for d in decoded] == [f"doc_{n}" for n in range(1_000)]
    assert list(decoded[7].vector.values) == [7.0] * 64
    assert decode_object(decoded[7].metadata) == {"n": 7}


def test_no_documents_make_no_frames():
    assert list(document_frames(iter(()))) == []

"""An in-memory owner of transfer/v1 sessions for overflow tests."""

from naas_abi_proto.transfer.v1 import transfer_pb2 as pb

OWNER = "a" * 32


class FakeHost:
    """The owner side of transfer/v1, enough for overflow uploads and downloads."""

    def __init__(self, parked: bytes = b"", chunk_bytes: int = 4, pending: int = 0):
        self.parked, self.chunk_bytes, self.pending = parked, chunk_bytes, pending
        self.uploads: dict[str, bytearray] = {}
        self.closed: list[str] = []
        self.subjects: list[str] = []
        self.read_offset = 0

    async def call(self, subject, request, response_type):
        self.subjects.append(subject)
        if isinstance(request, pb.OpenRequest):
            assert request.operation == "request"
            transfer_id = f"{OWNER}:{len(self.uploads)}"
            self.uploads[transfer_id] = bytearray()
            return pb.OpenResponse(
                id=transfer_id, chunk_bytes=min(request.chunk_bytes, self.chunk_bytes)
            )
        if isinstance(request, pb.WriteRequest):
            upload = self.uploads[request.id]
            assert len(request.data) <= self.chunk_bytes
            assert request.sequence == len(upload) // self.chunk_bytes
            upload.extend(request.data)
            return pb.WriteResponse()
        if isinstance(request, pb.ReadRequest):
            if self.pending:
                self.pending -= 1
                return pb.ReadResponse(pending=True, sequence=request.sequence)
            if self.read_offset >= len(self.parked):
                return pb.ReadResponse(done=True, sequence=request.sequence)
            data = self.parked[self.read_offset : self.read_offset + self.chunk_bytes]
            self.read_offset += len(data)
            return pb.ReadResponse(data=data, frame_end=True, sequence=request.sequence)
        if isinstance(request, pb.CloseRequest):
            self.closed.append(request.id)
            return pb.CloseResponse()
        raise AssertionError(f"unexpected {type(request).__name__}")

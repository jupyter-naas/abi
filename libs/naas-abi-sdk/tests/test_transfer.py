import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb

from naas_abi_sdk.transfer import Transfer, open_transfer


def test_chunk_sequences_frames_and_no_retry():
    async def scenario():
        call = AsyncMock(
            side_effect=[
                pb.WriteResponse(),
                pb.WriteResponse(),
                pb.ReadResponse(sequence=0, data=b"a"),
                pb.ReadResponse(sequence=1, data=b"b", frame_end=True),
                pb.ReadResponse(sequence=2, done=True),
            ]
        )
        transfer = Transfer(call, "prefix", "id", 2)
        await transfer.write(b"abc")
        assert [a.args[1].sequence for a in call.call_args_list] == [0, 1]
        assert [f async for f in transfer.frames()] == [b"ab"]
        call.side_effect = TimeoutError("uncertain")
        with pytest.raises(TimeoutError):
            await transfer.write(b"x")
        assert transfer.write_sequence == 2
        assert call.await_count == 6

    asyncio.run(scenario())


def test_close_preserves_original_failure():
    async def scenario():
        transport = SimpleNamespace(
            connect=AsyncMock(return_value=SimpleNamespace(max_payload=65536)),
            call=AsyncMock(
                side_effect=[
                    pb.OpenResponse(id="id", chunk_bytes=1024),
                    RuntimeError("close failed"),
                ]
            ),
        )
        with pytest.raises(ValueError, match="original"):
            async with open_transfer(transport, "prefix", "put"):
                raise ValueError("original")
        assert transport.call.call_args.args[0] == "prefix.close"

    asyncio.run(scenario())


def test_legacy_upload_handles_short_reads_and_bounds_buffering():
    import io

    from naas_abi_sdk.transfer import read_legacy_upload

    class ShortReader(io.BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 2))

    assert read_legacy_upload(ShortReader(b"hello"), 5) == b"hello"
    with pytest.raises(ValueError, match="upgrade required"):
        read_legacy_upload(ShortReader(b"too large"), 5)

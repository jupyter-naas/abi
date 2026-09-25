"""One bounded registry snapshot: CAS keeps graph validation and writes atomic."""

from naas_abi_core.services.discovery.discovery_ports import RevisionConflict
from nats.js.client import JetStreamContext
from nats.js.errors import KeyNotFoundError, KeyWrongLastSequenceError, NotFoundError
from nats.js.kv import KeyValue


class JetStreamRegistry:
    def __init__(self, js: JetStreamContext, bucket: KeyValue, name: str):
        self.js, self.bucket, self.name = js, bucket, name

    async def read(self) -> tuple[bytes, int]:
        try:
            # Reading through the stream leader avoids stale direct follower reads.
            entry = await self.js.get_msg(
                f"KV_{self.name}", subject=f"$KV.{self.name}.registry", direct=False
            )
        except (KeyNotFoundError, NotFoundError):
            return b"", 0
        return entry.data or b"", entry.seq or 0

    async def compare_and_swap(self, data: bytes, revision: int) -> None:
        try:
            await self.bucket.update("registry", data, last=revision)
        except KeyWrongLastSequenceError as exc:
            raise RevisionConflict() from exc

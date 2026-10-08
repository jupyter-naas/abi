from typing import Protocol


class RevisionConflict(Exception):
    pass


class RegistryPort(Protocol):
    async def read(self) -> tuple[bytes, int]: ...

    async def compare_and_swap(self, data: bytes, revision: int) -> None: ...

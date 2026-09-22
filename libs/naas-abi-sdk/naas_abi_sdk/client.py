"""Typed engine services sharing one NATS connection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from naas_abi_sdk.activity_log import ActivityLogClient
from naas_abi_sdk.bus import BusClient
from naas_abi_sdk.cache import CacheClient
from naas_abi_sdk.coding_environment import CodingEnvironmentClient
from naas_abi_sdk.dataset import DatasetClient
from naas_abi_sdk.document import DocumentClient
from naas_abi_sdk.email import EmailClient
from naas_abi_sdk.event import EventClient
from naas_abi_sdk.keyvalue import KeyvalueClient
from naas_abi_sdk.object_storage import ObjectStorageClient
from naas_abi_sdk.secret import SecretClient
from naas_abi_sdk.source_control import SourceControlClient
from naas_abi_sdk.transport import Transport
from naas_abi_sdk.triple_store import TripleStoreClient
from naas_abi_sdk.vector_store import VectorStoreClient


class ABIClient:
    def __init__(
        self,
        url: str,
        token: str | Callable[[], str],
        *,
        timeout: float = 10.0,
        **connection_options: Any,
    ) -> None:
        self._transport = Transport(url, token, timeout, **connection_options)
        self.bus = BusClient(self._transport)
        self.activity_log = ActivityLogClient(self._transport)
        self.cache = CacheClient(self._transport)
        self.coding_environment = CodingEnvironmentClient(self._transport)
        self.dataset = DatasetClient(self._transport)
        self.document = DocumentClient(self._transport)
        self.email = EmailClient(self._transport)
        self.event = EventClient(self._transport)
        self.keyvalue = KeyvalueClient(self._transport)
        self.object_storage = ObjectStorageClient(self._transport)
        self.secret = SecretClient(self._transport)
        self.source_control = SourceControlClient(self._transport)
        self.triple_store = TripleStoreClient(self._transport)
        self.vector_store = VectorStoreClient(self._transport)

    async def __aenter__(self) -> ABIClient:  # noqa: PYI034 - Python 3.10 without typing_extensions
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        """Release this client's connection; never shut down a remote service."""
        await self._transport.close()

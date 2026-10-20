"""Registry lookups return portable wrappers with optional LangChain proxies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

from naas_abi_sdk.model_registry import ModelRegistryClient

if TYPE_CHECKING:
    from naas_abi_sdk.models import RemoteModel


class ModelRegistryService:
    def __init__(self, client: ModelRegistryClient) -> None:
        self._client = client

    def _model(self, descriptor: pb.ModelDescriptor) -> RemoteModel:
        from naas_abi_sdk.models import remote_model

        return remote_model(self._client, descriptor)

    async def get(self, canonical_id: str, provider: str | None = None) -> RemoteModel:
        return await self._resolve(canonical_id, provider, "")

    async def get_chat_model(
        self, canonical_id: str, provider: str | None = None
    ) -> RemoteModel:
        return await self._resolve(canonical_id, provider, "chat")

    async def get_embedding_model(
        self, canonical_id: str, provider: str | None = None
    ) -> RemoteModel:
        return await self._resolve(canonical_id, provider, "embedding")

    async def get_default_chat_model(self) -> RemoteModel:
        return await self._resolve("", None, "chat")

    async def get_default_embedding_model(self) -> RemoteModel:
        return await self._resolve("", None, "embedding")

    async def _resolve(self, canonical_id, provider, kind):
        result = await self._client.resolve(
            pb.ResolveRequest(
                ref=pb.ModelRef(
                    canonical_id=canonical_id, provider=provider or "", kind=kind
                )
            )
        )
        return self._model(result.model)

    async def list_models(self) -> list[RemoteModel]:
        result = await self._client.list_models(pb.ListModelsRequest())
        return [self._model(model) for model in result.models]

    async def list_canonical_ids(self) -> list[str]:
        result = await self._client.list_models(pb.ListModelsRequest())
        return list(dict.fromkeys(model.ref.canonical_id for model in result.models))

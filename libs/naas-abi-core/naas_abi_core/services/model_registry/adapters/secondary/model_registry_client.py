"""Local registration at bootstrap; all model reads and inference cross NATS."""

from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.models.Model import ChatModel, EmbeddingModel
from naas_abi_core.services.model_registry.ModelRegistryPort import ModelNotFoundError
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_sdk.model_registry import ModelRegistryClient
from naas_abi_sdk.services.model_registry import ModelRegistryService as RemoteRegistry
from naas_abi_sdk.transport import RPCError, Transport


class ModelRegistryNATSClient(ModelRegistryService):
    def __init__(self, owner: ModelRegistryService, url: str, secret: str):
        super().__init__()
        self.owner = owner
        self.transport = Transport(
            url, lambda: issue_service_token("engine", secret), timeout=120
        )
        self.remote = RemoteRegistry(ModelRegistryClient(self.transport))

    def _call(self, coroutine):
        try:
            return nats_runtime.run_coro(coroutine, timeout=125)
        except RPCError as exc:
            if exc.code == "MODEL_NOT_FOUND":
                raise ModelNotFoundError(str(exc)) from exc
            raise

    @staticmethod
    def _wrap(value):
        kwargs = {
            "model_id": value.model_id,
            "provider": value.provider,
            "model": value.model,
            "name": value.name,
            "description": value.description,
        }
        if value.model_type == "chat":
            return ChatModel(
                **kwargs, context_window=value.metadata.get("context_window")
            )
        return EmbeddingModel(**kwargs, dimensions=value.metadata.get("dimensions"))

    def register(self, canonical_id, model):
        self.owner.register(canonical_id, model)

    def register_chat_provider(self, provider, factory):
        self.owner.register_chat_provider(provider, factory)

    def register_embedding_provider(self, provider, factory):
        self.owner.register_embedding_provider(provider, factory)

    def get(self, canonical_id, provider=None):
        return self._wrap(self._call(self.remote.get(canonical_id, provider)))

    def get_chat_model(self, canonical_id, provider=None):
        return self._wrap(
            self._call(self.remote.get_chat_model(canonical_id, provider))
        )

    def get_embedding_model(self, canonical_id, provider=None):
        return self._wrap(
            self._call(self.remote.get_embedding_model(canonical_id, provider))
        )

    def get_default_chat_model(self):
        return self._wrap(self._call(self.remote.get_default_chat_model()))

    def get_default_embedding_model(self):
        return self._wrap(self._call(self.remote.get_default_embedding_model()))

    @property
    def default_chat_model_id(self):
        from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

        return (
            self._call(
                self.remote._client.list_models(pb.ListModelsRequest())
            ).default_chat_model_id
            or None
        )

    @property
    def default_embedding_model_id(self):
        from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

        return (
            self._call(
                self.remote._client.list_models(pb.ListModelsRequest())
            ).default_embedding_model_id
            or None
        )

    def validate_defaults(self):
        self.owner.validate_defaults()

    def list_models(self):
        return [self._wrap(model) for model in self._call(self.remote.list_models())]

    def list_canonical_ids(self):
        return self._call(self.remote.list_canonical_ids())

    def list_registered_models(self):
        return [
            (model.canonical_id, self._wrap(model))
            for model in self._call(self.remote.list_models())
        ]

    def close(self):
        nats_runtime.run_coro(self.transport.close())

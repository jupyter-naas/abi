from typing import Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import \
    GenericLoader
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import \
    pydantic_model_validator
from naas_abi_core.services.KeyValue.KVPorts import IKVAdapter
from naas_abi_core.services.KeyValue.KVService import KVService
from pydantic import BaseModel, model_validator


class KVAdapterRedisConfiguration(BaseModel):
    """Redis KV adapter configuration.

    KV_adapter:
      adapter: "redis"
      config:
        redis_url: "{{ secret.REDIS_URL }}"
    """
    redis_url: str = "redis://localhost:6379"

class KVAdapterPythonConfiguration(BaseModel):
    """Python KV adapter configuration.

    KV_adapter:
      adapter: "python"
      config:
        python_url: "{{ secret.PYTHON_URL }}"
    """
    pass

class KVAdapterConfiguration(GenericLoader):
    adapter: Literal["redis", "python", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "KVAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "redis":
            pydantic_model_validator(
                KVAdapterRedisConfiguration,
                self.config,
                "Invalid configuration for services.KV.KV_adapter 'redis' adapter",
            )

        if self.adapter == "python":
            pydantic_model_validator(
                KVAdapterPythonConfiguration,
                self.config,
                "Invalid configuration for services.KV.KV_adapter 'python' adapter",
            )

        return self

    def load(self) -> IKVAdapter:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

            # Lazy import: only import when actually loading
            if self.adapter == "redis":
                from naas_abi_core.services.KeyValue.adapters.secondary.RedisAdapter import \
                    RedisAdapter

                return RedisAdapter(**self.config)
            elif self.adapter == "python":
                from naas_abi_core.services.KeyValue.adapters.secondary.PythonAdapter import \
                    PythonAdapter

                return PythonAdapter(**self.config)
            else:
                raise ValueError(f"Unknown adapter: {self.adapter}")
        else:
            return super().load()


class KVServiceConfiguration(BaseModel):
    kv_adapter: KVAdapterConfiguration

    def load(self) -> KVService:
        return KVService(adapter=self.kv_adapter.load())

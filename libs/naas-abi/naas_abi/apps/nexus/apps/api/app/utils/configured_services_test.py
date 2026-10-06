from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.utils.configured_services import configured_services
from pydantic import BaseModel


class _Adapter(BaseModel):
    adapter: str
    config: dict = {}


class _Store(BaseModel):
    store_adapter: _Adapter


class _Secrets(BaseModel):
    secret_adapters: list[_Adapter]


class _Registry(BaseModel):
    default_chat_model: str = "m"


class _Services(BaseModel):
    store: _Store = _Store(store_adapter=_Adapter(adapter="memory"))
    secret: _Secrets = _Secrets(secret_adapters=[])
    model_registry: _Registry = _Registry()


def test_lists_only_services_set_in_the_config() -> None:
    services = _Services.model_validate({"store": {"store_adapter": {"adapter": "qdrant"}}})
    assert configured_services(services) == [{"id": "store", "adapters": ["qdrant"]}]


def test_reads_single_and_multiple_adapters_and_services_without_one() -> None:
    services = _Services.model_validate(
        {
            "store": {"store_adapter": {"adapter": "redis"}},
            "secret": {"secret_adapters": [{"adapter": "dotenv"}, {"adapter": "naas"}]},
            "model_registry": {"default_chat_model": "qwen"},
        }
    )
    assert configured_services(services) == [
        {"id": "store", "adapters": ["redis"]},
        {"id": "secret", "adapters": ["dotenv", "naas"]},
        {"id": "model_registry", "adapters": []},
    ]


def test_never_exposes_adapter_config_values() -> None:
    services = _Services.model_validate(
        {"store": {"store_adapter": {"adapter": "s3", "config": {"secret_access_key": "hunter2"}}}}
    )
    assert "hunter2" not in repr(configured_services(services))

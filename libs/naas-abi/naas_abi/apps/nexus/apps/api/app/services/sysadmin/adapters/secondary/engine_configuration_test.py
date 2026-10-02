import uuid
from types import SimpleNamespace as NS

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.engine_configuration import (
    EngineServiceConfiguration,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceConfigurationSourceContract,
)

# A generated value the adapter must never echo (no literal credential in the repo).
CANARY = f"canary-{uuid.uuid4().hex}"


@pytest.fixture
def source():
    return EngineServiceConfiguration(
        NS(
            document=NS(document_adapter=NS(adapter="postgresql", config={"password": CANARY})),
            secret=NS(secret_adapters=[NS(adapter="dotenv"), NS(adapter="naas")]),
            cache=NS(adapters=[NS(adapter="redis", tier="hot"), NS(adapter="fs", tier="cold")]),
            model_registry=NS(defaults=NS(chat="gpt")),
        )
    )


class TestEngineServiceConfiguration(ServiceConfigurationSourceContract):
    pass


def test_never_exposes_adapter_settings(source):
    import asyncio

    assert CANARY not in repr(asyncio.run(source.list_configured()))


def test_services_without_adapters_are_listed_without_kinds(source):
    import asyncio

    services = {s.name: s for s in asyncio.run(source.list_configured())}
    assert services["model_registry"].adapters == ()


def test_reads_the_real_engine_services_model():
    import asyncio

    from naas_abi_core.engine.engine_configuration.EngineConfiguration import ServicesConfiguration

    services = {
        s.name: s
        for s in asyncio.run(EngineServiceConfiguration(ServicesConfiguration()).list_configured())
    }

    assert {
        "document",
        "object_storage",
        "triple_store",
        "kv",
        "cache",
        "secret",
        "model_registry",
    } <= set(services)
    assert all(services[name].adapters for name in ("document", "kv", "cache", "bus"))

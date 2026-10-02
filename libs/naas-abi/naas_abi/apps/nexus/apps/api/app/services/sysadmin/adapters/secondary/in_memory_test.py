import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory import (
    InMemoryEngineModules,
    InMemoryMicroServiceMonitor,
    InMemoryModuleRegistry,
    InMemoryNatsServerMonitor,
    InMemoryServiceConfiguration,
    UnavailableSource,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    EngineModuleSourceContract,
    MicroServiceMonitorContract,
    ModuleRegistryContract,
    NatsServerMonitorContract,
    ServiceConfigurationSourceContract,
    UnavailableMicroServiceMonitorContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures


@pytest.fixture
def source(request):
    if "EngineModule" in request.cls.__name__:
        return InMemoryEngineModules(fixtures.engine_modules())
    return InMemoryServiceConfiguration(fixtures.configured_services())


@pytest.fixture
def monitor(request):
    if "Unavailable" in request.cls.__name__:
        return UnavailableSource("nats", "NATS mode is off")
    if "Server" in request.cls.__name__:
        return InMemoryNatsServerMonitor(
            fixtures.nats_server(), fixtures.nats_connections(), fixtures.jetstream()
        )
    return InMemoryMicroServiceMonitor(fixtures.micro_instances())


@pytest.fixture
def registry():
    return InMemoryModuleRegistry(fixtures.remote_instances())


class TestInMemoryServiceConfiguration(ServiceConfigurationSourceContract):
    pass


class TestInMemoryEngineModules(EngineModuleSourceContract):
    pass


class TestInMemoryMicroServiceMonitor(MicroServiceMonitorContract):
    pass


class TestUnavailableSource(UnavailableMicroServiceMonitorContract):
    pass


class TestInMemoryModuleRegistry(ModuleRegistryContract):
    pass


class TestInMemoryNatsServerMonitor(NatsServerMonitorContract):
    pass

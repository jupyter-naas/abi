from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

SERVICES_DEPENDENCIES: dict[type, list[type]] = {
    TripleStoreService: [BusService],
    # EventService uses the bus for live broadcast on publish() and as the
    # transport for subscribe(); requesting the event service should pull
    # the bus in too.
    EventService: [BusService],
    # ObjectStorageService publishes ObjectPut / ObjectDeleted events on
    # every write; requesting object storage must pull the event service
    # (and transitively the bus) so those events are always captured.
    ObjectStorageService: [EventService],
}

# Services loaded on demand from module dependencies. In NATS mode they all load:
# the engine hosts them for every process on the bus, including remote SDK modules
# whose dependencies are declared at runtime, not in this engine's module list.
ON_DEMAND_SERVICES: tuple[type, ...] = (
    ActivityLogService,
    BusService,
    CacheService,
    DatasetService,
    DocumentService,
    EmailService,
    EventService,
    KeyValueService,
    ObjectStorageService,
    Secret,
    TripleStoreService,
    VectorStoreService,
)


# Each on-demand service and its name under ``services:`` in the configuration.
SERVICE_NAMES: dict[type, str] = {
    ActivityLogService: "activity_log",
    BusService: "bus",
    CacheService: "cache",
    DatasetService: "dataset",
    DocumentService: "document",
    EmailService: "email",
    EventService: "event",
    KeyValueService: "kv",
    ObjectStorageService: "object_storage",
    Secret: "secret",
    TripleStoreService: "triple_store",
    VectorStoreService: "vector_store",
}
# Loaded whatever the modules declare (see load_services).
ALWAYS_LOADED = ("coding_environment", "source_control")


class EngineServiceLoader:
    __configuration: EngineConfiguration

    def __init__(self, configuration: EngineConfiguration):
        self.__configuration = configuration

    def _should_load_service(
        self, service_type: type, services_to_load: list[type]
    ) -> bool:
        if service_type in services_to_load:
            return True

        # Walk SERVICES_DEPENDENCIES transitively so a chain like
        # ObjectStorageService -> EventService -> BusService loads all three.
        reachable: set[type] = set(services_to_load)
        frontier: list[type] = list(services_to_load)
        while frontier:
            current = frontier.pop()
            for dep in SERVICES_DEPENDENCIES.get(current, []):
                if dep not in reachable:
                    reachable.add(dep)
                    frontier.append(dep)
        return service_type in reachable

    def _load_bus(self) -> BusService:
        if self.__configuration.nats is None:
            return self.__configuration.services.bus.load()
        from naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter import (
            NATSJetStreamAdapter,
        )

        return BusService(
            NATSJetStreamAdapter(self.__configuration.nats.nats_url),
            emit_message_events=self.__configuration.services.bus.emit_message_events,
        )

    def local_backends(
        self, module_dependencies: dict[str, ModuleDependencies]
    ) -> dict[str, str]:
        """Of the services this engine will load, those whose data stays on this
        host, and where (docs/adr/20261006_single-serving-engine.md)."""
        services_to_load = self._services_to_load(module_dependencies)
        owned = [
            name
            for service_type, name in SERVICE_NAMES.items()
            if self._should_load_service(service_type, services_to_load)
        ]
        return self.__configuration.services.local_backends([*owned, *ALWAYS_LOADED])

    def _services_to_load(
        self, module_dependencies: dict[str, ModuleDependencies]
    ) -> list[type]:
        services_to_load: list[type] = []

        for module_dependency in module_dependencies.values():
            services_to_load.extend(module_dependency.services)

        if self.__configuration.nats is not None:
            services_to_load.extend(ON_DEMAND_SERVICES)

        if CacheService in services_to_load:
            for entry in self.__configuration.services.cache.adapters:
                if entry.adapter == "object_storage":
                    services_to_load.append(ObjectStorageService)
                elif entry.adapter == "keyvalue":
                    services_to_load.append(KeyValueService)
        if (
            ActivityLogService in services_to_load
            and self.__configuration.services.activity_log.activity_log_adapter.adapter
            == "document"
        ):
            services_to_load.append(DocumentService)
        return list(set(services_to_load))

    def load_services(
        self, module_dependencies: dict[str, ModuleDependencies]
    ) -> IEngine.Services:
        services_to_load = self._services_to_load(module_dependencies)
        logger.debug(f"Services to load: {services_to_load}")

        services = IEngine.Services(
            document=self.__configuration.services.document.load()
            if self._should_load_service(DocumentService, services_to_load)
            else None,
            object_storage=self.__configuration.services.object_storage.load()
            if self._should_load_service(ObjectStorageService, services_to_load)
            else None,
            dataset=self.__configuration.services.dataset.load()
            if self._should_load_service(DatasetService, services_to_load)
            else None,
            triple_store=self.__configuration.services.triple_store.load()
            if self._should_load_service(TripleStoreService, services_to_load)
            else None,
            vector_store=self.__configuration.services.vector_store.load()
            if self._should_load_service(VectorStoreService, services_to_load)
            else None,
            secret=self.__configuration.services.secret.load()
            if self._should_load_service(Secret, services_to_load)
            else None,
            bus=self._load_bus()
            if self._should_load_service(BusService, services_to_load)
            else None,
            kv=self.__configuration.services.kv.load()
            if self._should_load_service(KeyValueService, services_to_load)
            else None,
            email=self.__configuration.services.email.load()
            if self._should_load_service(EmailService, services_to_load)
            else None,
            cache=self.__configuration.services.cache.load()
            if self._should_load_service(CacheService, services_to_load)
            else None,
            activity_log=self.__configuration.services.activity_log.load()
            if self._should_load_service(ActivityLogService, services_to_load)
            else None,
            events=self.__configuration.services.event.load()
            if self._should_load_service(EventService, services_to_load)
            else None,
            # Always loaded: the registry is a cheap in-memory store that
            # modules populate during their on_load. Any module declaring a
            # ModelRegistryService dependency must be able to register against it.
            model_registry=self.__configuration.services.model_registry.load(),
            # Always loaded so the Nexus API resolvers can reach them; they
            # default to the cheap in_memory adapter when left unconfigured.
            coding_environment=self.__configuration.services.coding_environment.load(),
            source_control=self.__configuration.services.source_control.load(),
        )
        if self.__configuration.nats is None:
            services.wire_services()
        return services

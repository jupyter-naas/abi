from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Protocol, Union, runtime_checkable

from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

if TYPE_CHECKING:
    from naas_abi_core.module.Module import BaseModule


@runtime_checkable
class ServicesAware(Protocol):
    def set_services(self, services: "IEngine.Services") -> None: ...


class IEngine:
    class Services:
        __object_storage: ObjectStorageService | None
        __triple_store: TripleStoreService | None
        __vector_store: VectorStoreService | None
        __secret: Secret | None
        __bus: BusService | None
        __kv: KeyValueService | None

        def __init__(
            self,
            object_storage: ObjectStorageService | None = None,
            triple_store: TripleStoreService | None = None,
            vector_store: VectorStoreService | None = None,
            secret: Secret | None = None,
            bus: BusService | None = None,
            kv: KeyValueService | None = None,
        ):
            self.__object_storage = object_storage
            self.__triple_store = triple_store
            self.__vector_store = vector_store
            self.__secret = secret
            self.__bus = bus
            self.__kv = kv

        @property
        def kv(self) -> KeyValueService:
            assert self.__kv is not None, "KV service is not initialized"
            return self.__kv

        @property
        def object_storage(self) -> ObjectStorageService:
            assert self.__object_storage is not None, (
                "Object storage service is not initialized"
            )
            return self.__object_storage

        @property
        def triple_store(self) -> TripleStoreService:
            assert self.__triple_store is not None, (
                "Triple store service is not initialized"
            )
            return self.__triple_store

        def triple_store_available(self) -> bool:
            return self.__triple_store is not None

        @property
        def vector_store(self) -> VectorStoreService:
            assert self.__vector_store is not None, (
                "Vector store service is not initialized"
            )
            return self.__vector_store

        @property
        def secret(self) -> Secret:
            assert self.__secret is not None, "Secret service is not initialized"
            return self.__secret

        @property
        def bus(self) -> BusService:
            assert self.__bus is not None, "Bus service is not initialized"
            return self.__bus

        @property
        def all(
            self,
        ) -> List[
            Union[
                ObjectStorageService | None,
                TripleStoreService | None,
                VectorStoreService | None,
                Secret | None,
                BusService | None,
                KeyValueService | None,
            ]
        ]:
            return [
                self.__object_storage,
                self.__triple_store,
                self.__vector_store,
                self.__secret,
                self.__bus,
                self.__kv,
            ]

        def wire_services(self) -> None:
            """
            Wire the loaded services with references to the full set of engine services.

            This method iterates over all loaded engine services. For each service that implements
            the ServicesAware interface, it calls `set_services(self)` so that the service instance
            can access other engine services as needed. This ensures proper wiring and cross-service
            referencing, especially for services that depend on other services (such as bus, triple store, etc.).
            """
            for service in self.all:
                if service is None:
                    continue
                if isinstance(service, ServicesAware):
                    service.set_services(self)

    __services: Services
    __modules: Dict[str, BaseModule]

    @property
    def services(self) -> Services:
        return self.__services

    @property
    def modules(self) -> Dict[str, BaseModule]:
        return self.__modules

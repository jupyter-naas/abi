from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Union

from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

if TYPE_CHECKING:
    from naas_abi_core.module.Module import BaseModule


class IEngine:
    class Services:
        __object_storage: ObjectStorageService | None
        __triple_store: TripleStoreService | None
        __vector_store: VectorStoreService | None
        __secret: Secret | None

        def __init__(
            self,
            object_storage: ObjectStorageService | None = None,
            triple_store: TripleStoreService | None = None,
            vector_store: VectorStoreService | None = None,
            secret: Secret | None = None,
        ):
            self.__object_storage = object_storage
            self.__triple_store = triple_store
            self.__vector_store = vector_store
            self.__secret = secret

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
        def all(
            self,
        ) -> List[
            Union[
                ObjectStorageService | None,
                TripleStoreService | None,
                VectorStoreService | None,
                Secret | None,
            ]
        ]:
            return [
                self.__object_storage,
                self.__triple_store,
                self.__vector_store,
                self.__secret,
            ]

    __services: Services
    __modules: Dict[str, BaseModule]

    @property
    def services(self) -> Services:
        return self.__services

    @property
    def modules(self) -> Dict[str, BaseModule]:
        return self.__modules

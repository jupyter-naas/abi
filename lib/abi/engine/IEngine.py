from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Union

from abi.services.object_storage.ObjectStorageService import ObjectStorageService
from abi.services.secret.Secret import Secret
from abi.services.triple_store.TripleStoreService import TripleStoreService
from abi.services.vector_store.VectorStoreService import VectorStoreService

if TYPE_CHECKING:
    from abi.module.Module import BaseModule


class IEngine:
    class Services:
        __object_storage: ObjectStorageService
        __triple_store: TripleStoreService
        __vector_store: VectorStoreService
        __secret: Secret

        def __init__(
            self,
            object_storage: ObjectStorageService,
            triple_store: TripleStoreService,
            vector_store: VectorStoreService,
            secret: Secret,
        ):
            self.__object_storage = object_storage
            self.__triple_store = triple_store
            self.__vector_store = vector_store
            self.__secret = secret

        @property
        def object_storage(self) -> ObjectStorageService:
            return self.__object_storage

        @property
        def triple_store(self) -> TripleStoreService:
            return self.__triple_store

        @property
        def vector_store(self) -> VectorStoreService:
            return self.__vector_store

        @property
        def secret(self) -> Secret:
            return self.__secret

        @property
        def all(
            self,
        ) -> List[
            Union[ObjectStorageService, TripleStoreService, VectorStoreService, Secret]
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

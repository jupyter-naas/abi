from naas_abi_core.services.KeyValue.KVPorts import IKVAdapter
from naas_abi_core.services.ServiceBase import ServiceBase


class KVService(ServiceBase):
    __adapter: IKVAdapter

    def __init__(self, adapter: IKVAdapter):
        super().__init__()
        self.__adapter = adapter

    def get(self, key: str) -> bytes:
        return self.__adapter.get(key)

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        return self.__adapter.set(key, value, ttl)

    def set_if_not_exists(
        self,
        key: str,
        value: bytes,
        ttl: int | None = None,
    ) -> bool:
        return self.__adapter.set_if_not_exists(key, value, ttl)

    def delete(self, key: str) -> None:
        return self.__adapter.delete(key)

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        return self.__adapter.delete_if_value_matches(key, value)

    def exists(self, key: str) -> bool:
        return self.__adapter.exists(key)

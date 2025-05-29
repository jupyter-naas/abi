from abi.services.secret.SecretPorts import ISecretAdapter, ISecretService
from typing import Any, List, Dict


class Secret(ISecretService):
    """Secret service for managing and retrieving secrets.

    This service provides a unified interface for accessing secrets regardless of their storage location
    (environment variables, files, cloud services, etc.) through the use of adapters.

    Attributes:
        __adapter (ISecretAdapter): The adapter implementation used for retrieving secrets
            from the underlying storage system.

    Example:
        >>> secret_service = Secret(EnvVarSecretAdapter())
        >>> api_key = secret_service.get("API_KEY")
    """

    __adapters: List[ISecretAdapter]

    def __init__(self, adapters: List[ISecretAdapter]):
        self.__adapters = adapters

    def get(self, key: str, default: Any = None) -> str:
        for adapter in self.__adapters:
            value = adapter.get(key, None)

            if value is not None:
                return value

        return default
    
    def set(self, key: str, value: str):
        for adapter in self.__adapters:
            adapter.set(key, value)
    
    def remove(self, key: str):
        for adapter in self.__adapters:
            adapter.remove(key)
    
    def list(self) -> Dict[str, str]:
        secrets = {}

        for adapter in [adapter for adapter in self.__adapters][::-1]:
            secrets.update(adapter.list())

        return secrets

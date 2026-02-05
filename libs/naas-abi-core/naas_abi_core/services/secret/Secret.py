"""Secret Service Module

This module provides a unified interface for managing secrets across different storage systems.
The Secret service acts as a facade that coordinates multiple secret adapters, allowing applications
to retrieve, store, and manage secrets from various sources like environment variables, files,
cloud services, or other secret management systems.

The module implements the adapter pattern to support pluggable secret storage backends while
providing a consistent API for secret operations.

Classes:
    Secret: Main service class implementing ISecretService interface

Example:
    >>> from naas_abi_core.services.secret.adapters import EnvVarSecretAdapter, FileSecretAdapter
    >>> adapters = [EnvVarSecretAdapter(), FileSecretAdapter("/path/to/secrets")]
    >>> secret_service = Secret(adapters)
    >>> api_key = secret_service.get("API_KEY", "default_key")
"""

from typing import Any, Dict, List

from naas_abi_core.services.secret.SecretPorts import (ISecretAdapter,
                                                       ISecretService)
from naas_abi_core.services.ServiceBase import ServiceBase


class Secret(ServiceBase, ISecretService):
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
        super().__init__()
        self.__adapters = adapters

    def get(self, key: str, default: Any = None) -> str:
        """Retrieve a secret value by its key.

        Searches for the secret across all configured adapters in order. Returns the value
        from the first adapter that contains the key, or the default value if not found.

        Args:
            key (str): The secret key to retrieve.
            default (Any, optional): The value to return if the key is not found.
                Defaults to None.

        Returns:
            str: The secret value if found, otherwise the default value.

        Example:
            >>> secret_service = Secret([EnvVarSecretAdapter()])
            >>> database_url = secret_service.get("DATABASE_URL", "sqlite:///:memory:")
        """
        for adapter in self.__adapters:
            value = adapter.get(key, None)

            if value is not None:
                return value

        return default

    def set(self, key: str, value: str):
        """Set a secret value across all configured adapters.

        Stores the secret key-value pair in all adapters. This ensures consistency
        across different secret storage systems.

        Args:
            key (str): The secret key to set.
            value (str): The secret value to store.

        Note:
            If any adapter fails to set the value, the operation continues with
            remaining adapters. Consider implementing error handling based on
            your specific requirements.

        Example:
            >>> secret_service = Secret([EnvVarSecretAdapter(), FileSecretAdapter()])
            >>> secret_service.set("API_KEY", "your-secret-api-key")
        """
        for adapter in self.__adapters:
            adapter.set(key, value)

    def remove(self, key: str):
        """Remove a secret key from all configured adapters.

        Deletes the specified key from all adapters. This ensures the secret
        is completely removed from all storage systems.

        Args:
            key (str): The secret key to remove.

        Note:
            If any adapter fails to remove the key, the operation continues with
            remaining adapters. The method does not raise exceptions for missing keys.

        Example:
            >>> secret_service = Secret([EnvVarSecretAdapter(), FileSecretAdapter()])
            >>> secret_service.remove("OLD_API_KEY")
        """
        for adapter in self.__adapters:
            adapter.remove(key)

    def list(self) -> Dict[str, str | None]:
        """Retrieve all secrets from all configured adapters.

        Combines secrets from all adapters into a single dictionary. When the same
        key exists in multiple adapters, the value from the adapter with higher
        priority (earlier in the list) takes precedence.

        Returns:
            Dict[str, str]: A dictionary containing all secret key-value pairs.

        Note:
            The order of adapters matters for conflict resolution. Adapters are
            processed in reverse order, so earlier adapters override later ones.

        Example:
            >>> secret_service = Secret([EnvVarSecretAdapter(), FileSecretAdapter()])
            >>> all_secrets = secret_service.list()
            >>> print(f"Found {len(all_secrets)} secrets")
        """
        secrets = {}

        for adapter in [adapter for adapter in self.__adapters][::-1]:
            secrets.update(adapter.list())

        return secrets

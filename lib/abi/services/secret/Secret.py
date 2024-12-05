from abi.services.secret.SecretPorts import ISecretAdapter, ISecretService

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

    __adapter: ISecretAdapter
    
    def __init__(self, adapter: ISecretAdapter):
        self.__adapter = adapter

    def get(self, key: str, default: any = None) -> str:
        return self.__adapter.get(key)
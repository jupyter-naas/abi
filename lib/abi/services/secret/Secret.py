from abi.services.secret.SecretPorts import ISecretAdapter, ISecretService

class Secret(ISecretService):

    __adapter: ISecretAdapter
    
    def __init__(self, adapter: ISecretAdapter):
        self.__adapter = adapter

    def get(self, key: str, default: any = None) -> str:
        return self.__adapter.get(key)
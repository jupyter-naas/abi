from abc import ABC, abstractmethod

class ISecretAdapter(ABC):
    
    @abstractmethod
    def get(self, key: str) -> str:
        raise NotImplementedError()
    
    
class ISecretService(ABC):
    
    __adapter: ISecretAdapter
    
    @abstractmethod
    def get(self, key: str, default: any = None) -> str:
        raise NotImplementedError()
    

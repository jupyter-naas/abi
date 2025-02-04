from lib.abi.services.object_storage.ObjectStoragePort import IObjectStorageDomain, IObjectStorageAdapter, Exceptions

class ObjectStorageService(IObjectStorageDomain):
    adapter: IObjectStorageAdapter
    
    def __init__(self, adapter: IObjectStorageAdapter):
        self.adapter = adapter
        
    def get_object(self, prefix: str, key: str) -> bytes:
        return self.adapter.get_object(prefix, key)
    
    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.adapter.put_object(prefix, key, content)   
        
    def delete_object(self, prefix: str, key: str) -> None:
        self.adapter.delete_object(prefix, key)
        
    def list_objects(self, prefix: str = '') -> list[str]:
        if prefix == '/':
            prefix = ''

        return self.adapter.list_objects(prefix)
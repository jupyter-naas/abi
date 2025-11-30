from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNaas import (
    ObjectStorageSecondaryAdapterNaas,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3 import (
    ObjectStorageSecondaryAdapterS3,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.Storage import find_storage_folder


class ObjectStorageFactory:
    @staticmethod
    def ObjectStorageServiceFS__find_storage(
        needle: str = "storage",
    ) -> ObjectStorageService:
        import os

        return ObjectStorageService(
            ObjectStorageSecondaryAdapterFS(find_storage_folder(os.getcwd()))
        )

    @staticmethod
    def ObjectStorageServiceFS(base_path: str) -> ObjectStorageService:
        return ObjectStorageService(ObjectStorageSecondaryAdapterFS(base_path))

    @staticmethod
    def ObjectStorageServiceS3(
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        base_prefix: str,
        session_token: str | None = None,
    ) -> ObjectStorageService:
        return ObjectStorageService(
            ObjectStorageSecondaryAdapterS3(
                bucket_name,
                access_key_id,
                secret_access_key,
                base_prefix,
                session_token,
            )
        )

    @staticmethod
    def ObjectStorageServiceNaas(
        naas_api_key: str, workspace_id: str, storage_name: str, base_prefix: str = ""
    ) -> ObjectStorageService:
        return ObjectStorageService(
            ObjectStorageSecondaryAdapterNaas(
                naas_api_key, workspace_id, storage_name, base_prefix
            )
        )

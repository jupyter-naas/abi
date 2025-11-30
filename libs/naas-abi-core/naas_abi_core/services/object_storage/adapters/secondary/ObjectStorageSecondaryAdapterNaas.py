import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from queue import Queue
from typing import Optional

import pydash
import requests

# Load S3 secondary adapter as we will use it.
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3 import (
    ObjectStorageSecondaryAdapterS3,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    IObjectStorageAdapter,
)

NAAS_API_URL = "https://api.naas.ai/"
CREDENTIALS_EXPIRATION_TIME = timedelta(minutes=20)


@dataclass
class Credentials:
    bucket_name: str
    bucket_prefix: str
    access_key_id: str
    secret_key: str
    session_token: str
    region_name: str
    created_at: datetime


class ObjectStorageSecondaryAdapterNaas(IObjectStorageAdapter):
    __naas_api_key: str
    __workspace_id: str
    __storage_name: str
    __credentials: Credentials | None
    __s3_adapter: ObjectStorageSecondaryAdapterS3 | None

    def __init__(
        self,
        naas_api_key: str,
        workspace_id: str,
        storage_name: str,
        base_prefix: str = "",
    ):
        self.__naas_api_key = naas_api_key
        self.__workspace_id = workspace_id
        self.__storage_name = storage_name
        self.__base_prefix = base_prefix
        self.__credentials: Credentials | None = None
        self.__s3_adapter: ObjectStorageSecondaryAdapterS3 | None = None

    def ensure_credentials(self) -> Credentials:
        if self.__credentials is None:
            # TODO: Handle raise_for_status.
            self.__refresh_credentials()

        assert self.__credentials is not None

        # If credentials are older than 10 minutes, refresh them
        if self.__credentials.created_at < datetime.now() - CREDENTIALS_EXPIRATION_TIME:
            self.__refresh_credentials()

        return self.__credentials

    def __refresh_credentials(self) -> None:
        response = requests.post(
            f"{NAAS_API_URL}/workspace/{self.__workspace_id}/storage/credentials/",
            headers={"Authorization": f"Bearer {self.__naas_api_key}"},
            json={
                "name": self.__storage_name,
            },
        )

        response.raise_for_status()

        credentials = response.json()

        self.__credentials = Credentials(
            bucket_name=pydash.get(credentials, "credentials.s3.endpoint_url").split(
                "/"
            )[2],
            bucket_prefix="/".join(
                pydash.get(credentials, "credentials.s3.endpoint_url").split("/")[3:]
            ),
            access_key_id=pydash.get(credentials, "credentials.s3.access_key_id"),
            secret_key=pydash.get(credentials, "credentials.s3.secret_key"),
            session_token=pydash.get(credentials, "credentials.s3.session_token"),
            region_name=pydash.get(credentials, "credentials.s3.region_name"),
            created_at=datetime.now(),
        )

        # Re instantiate the S3 adapter with the new credentials
        self.__s3_adapter = ObjectStorageSecondaryAdapterS3(
            bucket_name=self.__credentials.bucket_name,
            access_key_id=self.__credentials.access_key_id,
            secret_access_key=self.__credentials.secret_key,
            base_prefix=os.path.join(
                self.__credentials.bucket_prefix, self.__base_prefix
            ),
            session_token=self.__credentials.session_token,
        )

    def get_object(self, prefix: str, key: str) -> bytes:
        self.ensure_credentials()

        assert self.__s3_adapter is not None

        return self.__s3_adapter.get_object(prefix, key)

    def put_object(self, prefix: str, key: str, content: bytes):
        self.ensure_credentials()

        assert self.__s3_adapter is not None

        return self.__s3_adapter.put_object(prefix, key, content)

    def delete_object(self, prefix: str, key: str):
        self.ensure_credentials()

        assert self.__s3_adapter is not None

        return self.__s3_adapter.delete_object(prefix, key)

    def list_objects(self, prefix: str, queue: Optional[Queue] = None) -> list[str]:
        self.ensure_credentials()

        assert self.__s3_adapter is not None

        return self.__s3_adapter.list_objects(prefix, queue)

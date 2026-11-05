"""Write to a Naas workspace storage, without core.

Core's ``ObjectStorageSecondaryAdapterNaas`` asks the Naas API for temporary S3
credentials of the storage, then writes with boto3 under the bucket prefix the
credentials name. Same here: credentials over httpx, the upload in a thread.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi_apps.common.http import HttpConfiguration, request_json

NAAS_API_URL = "https://api.naas.ai"
CREDENTIALS_LIFETIME = timedelta(minutes=20)


@dataclass
class Credentials:
    bucket_name: str
    bucket_prefix: str
    access_key_id: str
    secret_key: str
    session_token: str | None
    created_at: datetime


def parse_credentials(payload: dict[str, Any]) -> Credentials:
    s3 = payload["credentials"]["s3"]
    endpoint = s3["endpoint_url"]  # s3://<bucket>/<prefix...>
    return Credentials(
        bucket_name=endpoint.split("/")[2],
        bucket_prefix="/".join(endpoint.split("/")[3:]),
        access_key_id=s3["access_key_id"],
        secret_key=s3["secret_key"],
        session_token=s3.get("session_token"),
        created_at=datetime.now(UTC),
    )


def full_key(bucket_prefix: str, prefix: str, key: str) -> str:
    return "/".join(
        part.strip("/")
        for part in (bucket_prefix, prefix, key)
        if part and part.strip("/")
    )


class NaasStorage:
    def __init__(
        self,
        api_key: str,
        workspace_id: str,
        storage_name: str,
        http: HttpConfiguration | None = None,
        s3_client: Any = None,
    ) -> None:
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.storage_name = storage_name
        self.http = http or HttpConfiguration()
        self._s3_client = s3_client
        self._credentials: Credentials | None = None

    async def credentials(self) -> Credentials:
        if (
            self._credentials is None
            or self._credentials.created_at < datetime.now(UTC) - CREDENTIALS_LIFETIME
        ):
            payload = await request_json(
                self.http,
                "POST",
                f"{NAAS_API_URL}/workspace/{self.workspace_id}/storage/credentials/",
                service="Naas storage",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"name": self.storage_name},
            )
            self._credentials = parse_credentials(payload)
        return self._credentials

    def _client(self, credentials: Credentials) -> Any:
        if self._s3_client is not None:
            return self._s3_client
        import boto3

        return boto3.client(
            "s3",
            aws_access_key_id=credentials.access_key_id,
            aws_secret_access_key=credentials.secret_key,
            aws_session_token=credentials.session_token,
        )

    async def put_object(self, prefix: str, key: str, content: bytes) -> None:
        credentials = await self.credentials()
        client = self._client(credentials)
        await asyncio.to_thread(
            client.put_object,
            Bucket=credentials.bucket_name,
            Key=full_key(credentials.bucket_prefix, prefix, key),
            Body=content,
        )

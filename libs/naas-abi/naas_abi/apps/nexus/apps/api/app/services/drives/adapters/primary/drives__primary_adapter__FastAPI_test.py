"""``GET /api/platform/drives`` on a real IAM: the platform admin reads the File
System row (type, provider, location, status), nobody else does, and no credential
of the configuration is ever in the answer."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (  # noqa: E501
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.drives.adapters.primary.drives__primary_adapter__FastAPI import (  # noqa: E501
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.drives.adapters.secondary.object_storage import (
    ObjectStorageDrive,
)
from naas_abi.apps.nexus.apps.api.app.services.drives.runtime import get_drive_service
from naas_abi.apps.nexus.apps.api.app.services.drives.service import DriveService
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageAdapterConfiguration,
)

KEY_ID = "AKIA-KEY-ID"
SECRET = "s3cr3t-access-key"
TOKEN = "session-t0ken"

CONFIGURATION = ObjectStorageAdapterConfiguration(
    adapter="s3",
    config={
        "bucket_name": "abi",
        "base_prefix": "datastore",
        "access_key_id": KEY_ID,
        "secret_access_key": SECRET,
        "session_token": TOKEN,
        "endpoint_url": "http://minio:9000",
    },
)


class Storage:
    def __init__(self, error: BaseException | None = None):
        self.error = error

    def list_objects(self, prefix: str, queue=None) -> list[str]:
        if self.error is not None:
            raise self.error
        return []


def client(user: str, storage: Storage | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/platform/drives")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=user, email=f"{user}@example.com", name=user
    )
    source = ObjectStorageDrive(CONFIGURATION, lambda: storage or Storage())
    app.dependency_overrides[get_drive_service] = lambda: DriveService([source])
    return TestClient(app)


@pytest.fixture
def world(team):
    team.platform_admin("root")
    return team


def test_the_platform_admin_reads_the_file_system_row(world):
    response = client("root").get("/api/platform/drives")
    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "id": "file-system",
            "name": "File System",
            "type": "Object storage",
            "provider": "MinIO (S3-compatible)",
            "adapter": "s3",
            "location": [
                {"label": "bucket", "value": "abi"},
                {"label": "prefix", "value": "datastore"},
            ],
            "status": "reachable",
        }
    ]


def test_no_credential_is_ever_answered(world):
    for storage in (Storage(), Storage(RuntimeError(f"signature of {KEY_ID}:{SECRET} refused"))):
        text = client("root", storage).get("/api/platform/drives").text
        for secret in (KEY_ID, SECRET, TOKEN, "access_key", "secret", "token", "endpoint"):
            assert secret not in text


def test_a_storage_that_fails_is_unreachable(world):
    response = client("root", Storage(ConnectionError("refused"))).get("/api/platform/drives")
    assert response.status_code == 200
    assert response.json()[0]["status"] == "unreachable"


@pytest.mark.parametrize("user", ["owner", "admin", "member", "viewer", "stranger"])
def test_refused_to_anyone_but_a_platform_admin(world, user):
    response = client(user).get("/api/platform/drives")
    assert response.status_code == 403, response.text

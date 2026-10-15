from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    auth__primary_adapter__FastAPI as auth_adapter,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

NEW = "naas_abi/nexus/avatars"
LEGACY = "nexus/avatars"


@pytest.fixture
def storage(tmp_path) -> ObjectStorageService:
    return ObjectStorageService(adapter=ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path)))


def _exists(storage: ObjectStorageService, prefix: str, key: str) -> bool:
    try:
        storage.get_object(prefix, key)
        return True
    except Exceptions.ObjectNotFound:
        return False


def test_avatars_are_stored_under_naas_abi() -> None:
    assert auth_adapter.AVATAR_STORAGE_PREFIX == NEW
    assert auth_adapter.LEGACY_AVATAR_STORAGE_PREFIX == LEGACY


def test_an_avatar_is_read_from_the_new_location(storage: ObjectStorageService) -> None:
    storage.put_object(NEW, "user-1-a.png", b"new")
    assert auth_adapter._read_avatar(storage, "user-1-a.png") == b"new"


def test_a_legacy_avatar_is_served_and_moved(storage: ObjectStorageService) -> None:
    storage.put_object(LEGACY, "user-1-a.png", b"old")

    assert auth_adapter._read_avatar(storage, "user-1-a.png") == b"old"

    assert storage.get_object(NEW, "user-1-a.png") == b"old"
    assert not _exists(storage, LEGACY, "user-1-a.png")


def test_a_missing_avatar_is_not_found(storage: ObjectStorageService) -> None:
    with pytest.raises(Exceptions.ObjectNotFound):
        auth_adapter._read_avatar(storage, "nobody.png")


def test_deleting_an_avatar_clears_both_locations(storage: ObjectStorageService) -> None:
    storage.put_object(NEW, "user-1-a.png", b"new")
    storage.put_object(LEGACY, "user-1-a.png", b"old")

    auth_adapter._delete_old_avatar(storage, "/api/auth/avatar/user-1-a.png")

    assert not _exists(storage, NEW, "user-1-a.png")
    assert not _exists(storage, LEGACY, "user-1-a.png")


def test_drive_pictures_are_never_deleted_as_legacy(storage: ObjectStorageService) -> None:
    storage.put_object(NEW, "user-1?v=abc", b"kept")

    auth_adapter._delete_old_avatar(storage, "/api/auth/avatar/user/user-1?v=abc")

    assert _exists(storage, NEW, "user-1?v=abc")


def test_each_organization_picture_is_served_from_its_own_file(
    storage: ObjectStorageService,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    drive = "naas_abi/my-drive/user-1/.settings/avatar"
    storage.put_object(drive, "avatar_org_org-a.png", b"from-a")
    storage.put_object(drive, "avatar_org_org-b.png", b"from-b")
    app = FastAPI()
    app.include_router(auth_adapter.router)
    app.dependency_overrides[auth_adapter._get_object_storage] = lambda: storage
    client = TestClient(app)

    assert client.get("/avatar/user/user-1/org/org-a?v=1").content == b"from-a"
    assert client.get("/avatar/user/user-1/org/org-b?v=1").content == b"from-b"
    assert client.get("/avatar/user/user-1/org/org-c").status_code == 404
    assert client.get("/avatar/user/user-1/org/..%2Fx").status_code == 404

"""A user committed through the ORM gets a .manifest.json and default folders in My Drive.

Runs against a real SQLite session and a filesystem ObjectStorage.
"""

from __future__ import annotations

import datetime
import json

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import UserModel
from naas_abi.apps.nexus.apps.api.app.services.files.drives.my_drive import (
    DEFAULT_FOLDERS,
    DEFAULT_FOLDERS_MARKER_ROOT,
    MANIFEST_NAME,
    MyDriveWriter,
    backfill_my_drives,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

T0 = datetime.datetime(2026, 5, 1, 9, 30)
ROOT = "naas_abi/my-drive/user-1"


@pytest_asyncio.fixture
async def env(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(UserModel.__table__.create)
    storage = ObjectStorageService(
        adapter=ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path / "datastore"))
    )
    writer = MyDriveWriter(get_storage=lambda: storage)
    writer.install()
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield maker, storage
    finally:
        writer.uninstall()
        await engine.dispose()


def _user(user_id: str = "user-1") -> UserModel:
    return UserModel(
        id=user_id,
        email=f"{user_id}@example.com",
        name="Ada",
        hashed_password="x",
        created_at=T0,
        updated_at=T0,
    )


def _has(storage: ObjectStorageService, prefix: str, key: str) -> bool:
    try:
        storage.get_object(prefix, key)
        return True
    except Exceptions.ObjectNotFound:
        return False


def _manifest(storage: ObjectStorageService, root: str = ROOT) -> dict:
    return json.loads(storage.get_object(root, MANIFEST_NAME))


@pytest.mark.asyncio
async def test_a_created_user_gets_a_manifest_and_the_default_folders(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        await session.commit()

    assert _manifest(storage) == {
        "schema_version": 1,
        "user": {
            "id": "user-1",
            "name": "Ada",
            "email": "user-1@example.com",
            "created_at": "2026-05-01T09:30:00",
            "updated_at": "2026-05-01T09:30:00",
        },
    }
    assert set(DEFAULT_FOLDERS) == {"downloads", "uploads", "documents"}
    for folder in DEFAULT_FOLDERS:
        assert _has(storage, f"{ROOT}/{folder}", ".nexus_folder")
    assert _has(storage, DEFAULT_FOLDERS_MARKER_ROOT, "user-1")


@pytest.mark.asyncio
async def test_a_rolled_back_user_gets_nothing(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        await session.flush()
        await session.rollback()

    assert not _has(storage, ROOT, MANIFEST_NAME)
    assert not _has(storage, f"{ROOT}/uploads", ".nexus_folder")


@pytest.mark.asyncio
async def test_renaming_a_user_rewrites_the_manifest(env) -> None:
    maker, storage = env
    async with maker() as session:
        user = _user()
        session.add(user)
        await session.commit()

        user.name = "Ada Lovelace"
        await session.commit()

    assert _manifest(storage)["user"]["name"] == "Ada Lovelace"


@pytest.mark.asyncio
async def test_other_profile_changes_leave_the_manifest_and_deleted_folders(env) -> None:
    maker, storage = env
    async with maker() as session:
        user = _user()
        session.add(user)
        await session.commit()
        storage.put_object(ROOT, MANIFEST_NAME, b'{"edited": true}')
        storage.delete_object(f"{ROOT}/downloads", ".nexus_folder")

        user.bio = "Mathematician"
        await session.commit()

    assert _manifest(storage) == {"edited": True}
    assert not _has(storage, f"{ROOT}/downloads", ".nexus_folder")


@pytest.mark.asyncio
async def test_backfill_writes_what_is_missing_once(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user("user-1"))
        session.add(_user("user-2"))
        await session.commit()
    # user-1 predates the writer; user-2 is set up and deleted its documents folder.
    storage.delete_object(ROOT, MANIFEST_NAME)
    storage.delete_object(DEFAULT_FOLDERS_MARKER_ROOT, "user-1")
    storage.delete_object(f"{ROOT}/uploads", ".nexus_folder")
    storage.delete_object("naas_abi/my-drive/user-2/documents", ".nexus_folder")

    async with maker() as session:
        written = await backfill_my_drives(session, storage)

    assert written == {"manifests": 1, "default_folders": 1}
    assert _manifest(storage)["user"]["id"] == "user-1"
    assert _has(storage, f"{ROOT}/uploads", ".nexus_folder")
    assert not _has(storage, "naas_abi/my-drive/user-2/documents", ".nexus_folder")


@pytest.mark.asyncio
async def test_a_storage_failure_does_not_break_the_commit(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(UserModel.__table__.create)

    def broken_storage() -> ObjectStorageService:
        raise RuntimeError("object storage is down")

    writer = MyDriveWriter(get_storage=broken_storage)
    writer.install()
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add(_user())
            await session.commit()
        async with maker() as session:
            assert await session.get(UserModel, "user-1") is not None
    finally:
        writer.uninstall()
        await engine.dispose()

"""A workspace committed through the ORM gets a manifest.json and staff folders in its drive.

Runs against a real SQLite session and a filesystem ObjectStorage.
"""

from __future__ import annotations

import datetime
import json

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.files.workspace_drive import (
    LEGACY_MANIFEST_NAME,
    MANIFEST_NAME,
    README_NAME,
    STAFF_FOLDERS,
    STAFF_FOLDERS_MARKER_ROOT,
    WorkspaceDriveWriter,
    backfill_workspace_drives,
    staff_folder_readme,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

T0 = datetime.datetime(2026, 5, 1, 9, 30)


@pytest_asyncio.fixture
async def env(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    async with engine.begin() as conn:
        for model in (UserModel, OrganizationModel, WorkspaceModel):
            await conn.run_sync(model.__table__.create)
    storage = ObjectStorageService(
        adapter=ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path / "datastore"))
    )
    writer = WorkspaceDriveWriter(get_storage=lambda: storage)
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


def _workspace(workspace_id: str = "ws-1", **fields) -> WorkspaceModel:
    return WorkspaceModel(
        id=workspace_id,
        name=fields.pop("name", "Forvis Mazars France"),
        slug=fields.pop("slug", workspace_id),
        owner_id="user-1",
        created_at=T0,
        updated_at=T0,
        **fields,
    )


def _manifest(storage: ObjectStorageService, workspace_id: str) -> dict:
    content = storage.get_object(f"naas_abi/workspace-drive/{workspace_id}", MANIFEST_NAME)
    return json.loads(content)


@pytest.mark.asyncio
async def test_a_created_workspace_gets_a_manifest(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        session.add(_workspace(slug="forvis-mazars-france"))
        await session.commit()

    assert _manifest(storage, "ws-1") == {
        "schema_version": 1,
        "workspace": {
            "id": "ws-1",
            "name": "Forvis Mazars France",
            "slug": "forvis-mazars-france",
            "organization_id": None,
            "owner_id": "user-1",
            "created_at": "2026-05-01T09:30:00",
            "updated_at": "2026-05-01T09:30:00",
        },
    }


@pytest.mark.asyncio
async def test_a_rolled_back_workspace_gets_no_manifest(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        session.add(_workspace())
        await session.flush()
        await session.rollback()

    with pytest.raises(Exceptions.ObjectNotFound):
        storage.get_object("naas_abi/workspace-drive/ws-1", MANIFEST_NAME)


@pytest.mark.asyncio
async def test_updating_a_workspace_rewrites_the_manifest(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        workspace = _workspace()
        session.add(workspace)
        await session.commit()

        workspace.name = "Renamed"
        workspace.slug = "renamed"
        await session.commit()

    workspace_meta = _manifest(storage, "ws-1")["workspace"]
    assert workspace_meta["name"] == "Renamed"
    assert workspace_meta["slug"] == "renamed"
    assert workspace_meta["created_at"] == "2026-05-01T09:30:00"
    assert workspace_meta["updated_at"] > "2026-05-01T09:30:00"


@pytest.mark.asyncio
async def test_a_rolled_back_update_leaves_the_manifest(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        workspace = _workspace()
        session.add(workspace)
        await session.commit()

        workspace.name = "Renamed"
        await session.flush()
        await session.rollback()

    assert _manifest(storage, "ws-1")["workspace"]["name"] == "Forvis Mazars France"


@pytest.mark.asyncio
async def test_backfill_writes_only_the_missing_manifests(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        session.add(_workspace("ws-1"))
        session.add(_workspace("ws-2"))
        await session.commit()
    # ws-1 predates the writer; ws-2 already has a manifest someone edited.
    storage.delete_object("naas_abi/workspace-drive/ws-1", MANIFEST_NAME)
    storage.put_object("naas_abi/workspace-drive/ws-2", MANIFEST_NAME, b'{"edited": true}')

    async with maker() as session:
        written = await backfill_workspace_drives(session, storage)

    assert written["manifests"] == 1
    assert _manifest(storage, "ws-1")["workspace"]["id"] == "ws-1"
    assert _manifest(storage, "ws-2") == {"edited": True}


@pytest.mark.asyncio
async def test_a_storage_failure_does_not_break_the_commit(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    async with engine.begin() as conn:
        for model in (UserModel, OrganizationModel, WorkspaceModel):
            await conn.run_sync(model.__table__.create)

    def broken_storage() -> ObjectStorageService:
        raise RuntimeError("object storage is down")

    writer = WorkspaceDriveWriter(get_storage=broken_storage)
    writer.install()
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add(_user())
            session.add(_workspace())
            await session.commit()
        async with maker() as session:
            assert await session.get(WorkspaceModel, "ws-1") is not None
    finally:
        writer.uninstall()
        await engine.dispose()


def _readme(storage: ObjectStorageService, workspace_id: str, folder: str) -> str:
    prefix = f"naas_abi/workspace-drive/{workspace_id}/{folder}"
    return storage.get_object(prefix, README_NAME).decode("utf-8")


def _has(storage: ObjectStorageService, prefix: str, key: str) -> bool:
    try:
        storage.get_object(prefix, key)
        return True
    except Exceptions.ObjectNotFound:
        return False


def test_every_staff_folder_has_a_readme_with_the_shared_layout() -> None:
    assert len(STAFF_FOLDERS) == 9
    for folder in STAFF_FOLDERS:
        readme = staff_folder_readme(folder)
        assert readme.startswith("# S")
        assert "## How this drive is organized" in readme
        assert f"`{folder}/`" in readme


@pytest.mark.asyncio
async def test_a_created_workspace_gets_the_staff_folders(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        session.add(_workspace())
        await session.commit()

    for folder in STAFF_FOLDERS:
        assert _readme(storage, "ws-1", folder) == staff_folder_readme(folder)
        assert _has(storage, f"naas_abi/workspace-drive/ws-1/{folder}", ".nexus_folder")
    assert _has(storage, STAFF_FOLDERS_MARKER_ROOT, "ws-1")


@pytest.mark.asyncio
async def test_updating_a_workspace_does_not_recreate_a_deleted_staff_folder(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        workspace = _workspace()
        session.add(workspace)
        await session.commit()
        storage.delete_object("naas_abi/workspace-drive/ws-1/logistics", README_NAME)

        workspace.name = "Renamed"
        await session.commit()

    assert not _has(storage, "naas_abi/workspace-drive/ws-1/logistics", README_NAME)


@pytest.mark.asyncio
async def test_backfill_creates_staff_folders_once_and_keeps_existing_files(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        session.add(_workspace("ws-1"))
        session.add(_workspace("ws-2"))
        await session.commit()
    # ws-1 predates the writer, with its own README in finance/; ws-2 is set up and a
    # user deleted its training/ README.
    storage.delete_object(STAFF_FOLDERS_MARKER_ROOT, "ws-1")
    storage.put_object("naas_abi/workspace-drive/ws-1/finance", README_NAME, b"# Ours")
    storage.delete_object("naas_abi/workspace-drive/ws-1/plans", README_NAME)
    storage.delete_object("naas_abi/workspace-drive/ws-2/training", README_NAME)

    async with maker() as session:
        written = await backfill_workspace_drives(session, storage)

    assert written == {"manifests": 0, "staff_folders": 1, "legacy_manifests_removed": 0}
    assert _readme(storage, "ws-1", "plans") == staff_folder_readme("plans")
    assert _readme(storage, "ws-1", "finance") == "# Ours"
    assert not _has(storage, "naas_abi/workspace-drive/ws-2/training", README_NAME)


def test_the_manifest_is_a_dot_file() -> None:
    assert MANIFEST_NAME == ".manifest.json"


@pytest.mark.asyncio
async def test_backfill_removes_legacy_manifests_it_wrote_and_keeps_user_files(env) -> None:
    maker, storage = env
    async with maker() as session:
        session.add(_user())
        session.add(_workspace("ws-1"))
        session.add(_workspace("ws-2"))
        await session.commit()
    legacy = json.dumps({"schema_version": 1, "workspace": {"id": "ws-1"}}).encode()
    storage.put_object("naas_abi/workspace-drive/ws-1", LEGACY_MANIFEST_NAME, legacy)
    storage.put_object("naas_abi/workspace-drive/ws-2", LEGACY_MANIFEST_NAME, b'{"mine": 1}')

    async with maker() as session:
        written = await backfill_workspace_drives(session, storage)

    assert written["legacy_manifests_removed"] == 1
    assert not _has(storage, "naas_abi/workspace-drive/ws-1", LEGACY_MANIFEST_NAME)
    assert _has(storage, "naas_abi/workspace-drive/ws-1", MANIFEST_NAME)
    assert _has(storage, "naas_abi/workspace-drive/ws-2", LEGACY_MANIFEST_NAME)

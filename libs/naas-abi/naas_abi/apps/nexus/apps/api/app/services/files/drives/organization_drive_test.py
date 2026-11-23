"""An organization committed through the ORM gets a manifest and the staff folders in
its drive, and the organizations that predate it get them at start.

Runs against a real SQLite session and a filesystem ObjectStorage.
"""

from __future__ import annotations

import datetime
import json

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, UserModel
from naas_abi.apps.nexus.apps.api.app.services.files.drives.organization_drive import (
    ORGANIZATION_STAFF_MARKER_ROOT,
    OrganizationDriveWriter,
    backfill_organization_drives,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.manifest import MANIFEST_NAME
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.staff_folders import (
    README_NAME,
    STAFF_FOLDERS,
    staff_folder_readme,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

T0 = datetime.datetime(2026, 5, 1, 9, 30)
ROOT = "naas_abi/organization-drive"


@pytest_asyncio.fixture
async def env(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    async with engine.begin() as conn:
        for model in (UserModel, OrganizationModel):
            await conn.run_sync(model.__table__.create)
    storage = ObjectStorageService(
        adapter=ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path / "datastore"))
    )
    writer = OrganizationDriveWriter(get_storage=lambda: storage)
    writer.install()
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield maker, storage, writer
    finally:
        writer.uninstall()
        await engine.dispose()


def _user() -> UserModel:
    return UserModel(
        id="user-1", email="user-1@example.com", name="Ada", created_at=T0, updated_at=T0
    )


def _organization(org_id: str = "org-1", **fields) -> OrganizationModel:
    return OrganizationModel(
        id=org_id,
        name=fields.pop("name", "Acme"),
        slug=fields.pop("slug", org_id),
        owner_id="user-1",
        created_at=T0,
        updated_at=T0,
        **fields,
    )


def _manifest(storage: ObjectStorageService, org_id: str) -> dict:
    return json.loads(storage.get_object(f"{ROOT}/{org_id}", MANIFEST_NAME))


def _exists(storage: ObjectStorageService, prefix: str, key: str) -> bool:
    try:
        storage.get_object(prefix, key)
        return True
    except Exceptions.ObjectNotFound:
        return False


@pytest.mark.asyncio
async def test_a_created_organization_gets_a_manifest_and_the_staff_folders(env) -> None:
    maker, storage, _ = env
    async with maker() as session:
        session.add(_user())
        session.add(_organization(slug="acme"))
        await session.commit()

    assert _manifest(storage, "org-1") == {
        "schema_version": 1,
        "organization": {
            "id": "org-1",
            "name": "Acme",
            "slug": "acme",
            "owner_id": "user-1",
            "created_at": "2026-05-01T09:30:00",
            "updated_at": "2026-05-01T09:30:00",
        },
    }
    for folder in STAFF_FOLDERS:
        prefix = f"{ROOT}/org-1/{folder}"
        assert _exists(storage, prefix, FilesService.folder_marker)
        assert storage.get_object(prefix, README_NAME).decode() == staff_folder_readme(folder)
    assert _exists(storage, ORGANIZATION_STAFF_MARKER_ROOT, "org-1")


@pytest.mark.asyncio
async def test_a_rolled_back_organization_gets_no_drive(env) -> None:
    maker, storage, _ = env
    async with maker() as session:
        session.add(_user())
        session.add(_organization())
        await session.flush()
        await session.rollback()

    assert not _exists(storage, f"{ROOT}/org-1", MANIFEST_NAME)
    assert not _exists(storage, ORGANIZATION_STAFF_MARKER_ROOT, "org-1")


@pytest.mark.asyncio
async def test_renaming_rewrites_the_manifest_and_brings_no_deleted_folder_back(env) -> None:
    maker, storage, _ = env
    async with maker() as session:
        session.add(_user())
        session.add(_organization())
        await session.commit()
    storage.delete_object(f"{ROOT}/org-1/plans", README_NAME)
    storage.delete_object(f"{ROOT}/org-1/plans", FilesService.folder_marker)

    async with maker() as session:
        organization = await session.get(OrganizationModel, "org-1")
        organization.name = "Acme Group"
        await session.commit()

    assert _manifest(storage, "org-1")["organization"]["name"] == "Acme Group"
    assert not _exists(storage, f"{ROOT}/org-1/plans", README_NAME)


@pytest.mark.asyncio
async def test_the_backfill_gives_older_organizations_their_drive_once(env) -> None:
    maker, storage, writer = env
    writer.uninstall()  # organizations made before the writer existed
    async with maker() as session:
        session.add(_user())
        session.add(_organization("org-1"))
        session.add(_organization("org-2", name="Globex"))
        await session.commit()
    assert not _exists(storage, f"{ROOT}/org-1", MANIFEST_NAME)

    async with maker() as session:
        assert await backfill_organization_drives(session, storage) == {
            "manifests": 2,
            "staff_folders": 2,
        }
    assert _manifest(storage, "org-2")["organization"]["name"] == "Globex"
    assert _exists(storage, f"{ROOT}/org-2/finance", README_NAME)

    async with maker() as session:
        assert await backfill_organization_drives(session, storage) == {
            "manifests": 0,
            "staff_folders": 0,
        }

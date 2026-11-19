from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, UserModel
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationUpdateInput,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        for model in (UserModel, OrganizationModel):
            await conn.run_sync(lambda sync, m=model: m.__table__.create(sync))
    async with AsyncSession(engine) as session:
        session.add(
            UserModel(
                id="alice", email="alice@example.com", name="Alice", created_at=NOW, updated_at=NOW
            )
        )
        session.add(
            OrganizationModel(
                id="org-a",
                name="Acme",
                slug="acme",
                owner_id="alice",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_an_organization_has_no_identity_until_set(db: AsyncSession) -> None:
    record = await OrganizationSecondaryAdapterPostgres(db=db).get_organization_by_id("org-a")
    assert record is not None
    assert (record.legal_name, record.website, record.city, record.country) == (
        None,
        None,
        None,
        None,
    )


@pytest.mark.asyncio
async def test_the_identity_is_stored_and_read_back(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    identity = {
        "legal_name": "Acme Holding SAS",
        "registration_number": "123 456 789",
        "vat_number": "FR12345678901",
        "website": "https://acme.example",
        "contact_email": "hello@acme.example",
        "address_line1": "1 rue de la Paix",
        "address_line2": "Bâtiment B",
        "postal_code": "75002",
        "city": "Paris",
        "country": "France",
    }
    updated = await adapter.update_organization(
        "org-a", OrganizationUpdateInput(**identity, set_fields=set(identity))
    )
    assert updated is not None
    assert {field: getattr(updated, field) for field in identity} == identity
    assert updated.name == "Acme"


@pytest.mark.asyncio
async def test_a_field_set_to_none_is_cleared(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    await adapter.update_organization(
        "org-a",
        OrganizationUpdateInput(city="Paris", country="France", set_fields={"city", "country"}),
    )
    cleared = await adapter.update_organization(
        "org-a", OrganizationUpdateInput(city=None, set_fields={"city"})
    )
    assert cleared is not None
    assert (cleared.city, cleared.country) == (None, "France")


@pytest.mark.asyncio
async def test_the_time_zone_is_utc_until_set_then_kept(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    assert (await adapter.get_organization_by_id("org-a")).timezone == "UTC"
    updated = await adapter.update_organization(
        "org-a",
        OrganizationUpdateInput(timezone="Europe/Paris", set_fields={"timezone"}),
    )
    assert updated is not None and updated.timezone == "Europe/Paris"
    assert (await adapter.get_organization_by_id("org-a")).timezone == "Europe/Paris"

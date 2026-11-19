"""An organization's domain is verified only with proof of control (a DNS TXT record)
or a platform administrator's word; public mail domains are no organization's, and
another organization's unverified claim never keeps the domain from its owner. Real
routes, PostgreSQL adapter (on SQLite) and IAM."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import UserModel
from naas_abi.apps.nexus.apps.api.app.services.organizations import domain_proof
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as org_api,
)


@pytest.fixture
def world(nexus_db, nexus_iam):
    import asyncio

    async def people() -> None:
        async with nexus_db() as db:
            for uid in ("pat", "olivia", "root"):
                db.add(UserModel(id=uid, email=f"{uid}@people.test", name=uid.title()))
            await db.commit()

    asyncio.run(people())
    for uid in ("pat", "olivia"):
        nexus_iam.user(uid)
    nexus_iam.platform_admin("root")
    published: dict[str, list[str]] = {}

    def as_(user: str) -> TestClient:
        async def db_dep():
            async with nexus_db() as session:
                yield session
                await session.commit()

        app = FastAPI()
        app.include_router(org_api.router, prefix="/organizations")
        app.dependency_overrides[get_db] = db_dep
        app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
            id=user, name=user.title(), is_superadmin=False
        )
        return TestClient(app)

    def org(user: str, slug: str) -> str:
        made = as_(user).post("/organizations", json={"name": slug.title(), "slug": slug})
        assert made.status_code == 200, made.text
        return made.json()["id"]

    def publish(domain: dict) -> None:
        published.setdefault(domain["verification_record"], []).append(domain["verification_token"])

    return SimpleNamespace(as_=as_, org=org, publish=publish, published=published)


@pytest.fixture(autouse=True)
def dns(world, monkeypatch):
    monkeypatch.setattr(domain_proof, "txt_records", lambda name: world.published.get(name, []))


def test_a_domain_keeps_unverified_without_its_proof(world) -> None:
    org = world.org("pat", "pat")
    http = world.as_("pat")
    added = http.post(f"/organizations/{org}/domains", json={"domain": "acme.example"})
    assert added.status_code == 200, added.text
    claim = added.json()
    assert claim["is_verified"] is False
    assert claim["verification_record"] == "_nexus-verify.acme.example"
    assert http.post(f"/organizations/{org}/domains/{claim['id']}/verify").status_code == 400
    # Its record published: verified.
    world.publish(claim)
    verified = http.post(f"/organizations/{org}/domains/{claim['id']}/verify")
    assert verified.status_code == 200 and verified.json()["is_verified"] is True


def test_a_platform_administrator_vouches_for_a_domain(world) -> None:
    org = world.org("olivia", "olivia")
    claim = world.as_("olivia").post(
        f"/organizations/{org}/domains", json={"domain": "olivia.example"}
    )
    vouched = world.as_("root").post(f"/organizations/{org}/domains/{claim.json()['id']}/verify")
    assert vouched.status_code == 200 and vouched.json()["is_verified"] is True


@pytest.mark.parametrize("domain", ["gmail.com", "outlook.com", "localhost"])
def test_public_mail_domains_keep_to_no_organization(world, domain) -> None:
    org = world.org("pat", "pat")
    added = world.as_("pat").post(f"/organizations/{org}/domains", json={"domain": domain})
    assert added.status_code == 400


def test_an_unverified_claim_never_keeps_a_domain_from_its_owner(world) -> None:
    first = world.org("pat", "pat")
    owner = world.org("olivia", "olivia")
    claimed = world.as_("pat").post(
        f"/organizations/{first}/domains", json={"domain": "olivia.example"}
    )
    assert claimed.status_code == 200
    # The owner claims it in turn, publishes its record, and adding it verifies it.
    claim = world.as_("olivia").post(
        f"/organizations/{owner}/domains", json={"domain": "olivia.example"}
    )
    assert claim.status_code == 200, claim.text
    world.publish(claim.json())
    again = world.as_("olivia").post(
        f"/organizations/{owner}/domains", json={"domain": "olivia.example"}
    )
    assert again.status_code == 200 and again.json()["is_verified"] is True
    # The token is the organization's: claiming again keeps the record valid.
    assert again.json()["id"] == claim.json()["id"]
    assert world.as_("pat").get(f"/organizations/{first}/domains").json() == []
    retaken = world.as_("pat").post(
        f"/organizations/{first}/domains", json={"domain": "olivia.example"}
    )
    assert retaken.status_code == 400


def _legacy_domains(nexus_db, *rows: tuple[str, str, bool]) -> None:
    """``(domain, organization, verified)`` rows an older version stored, routed to
    the provider ``corp-sso``."""
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.models import OrganizationDomainModel

    async def add() -> None:
        async with nexus_db() as db:
            for index, (domain, org, verified) in enumerate(rows):
                db.add(
                    OrganizationDomainModel(
                        id=f"legacy-{index}",
                        organization_id=org,
                        domain=domain,
                        is_verified=verified,
                        provider="corp-sso",
                    )
                )
            await db.commit()

    asyncio.run(add())


def test_a_public_mail_domain_routes_no_sign_in_whatever_an_older_claim_says(
    world, nexus_db
) -> None:
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.postgres import (
        OidcSessionSecondaryAdapterPostgres,
    )
    from naas_abi.apps.nexus.apps.api.app.services.oidc.service import OidcSignInService

    org = world.org("pat", "pat")
    _legacy_domains(nexus_db, ("gmail.com", org, True), ("Corp.example", org, True))

    async def route(email: str) -> str | None:
        async def providers():
            return [], "default-idp"

        async with nexus_db() as db:
            service = SimpleNamespace(
                adapter=OidcSessionSecondaryAdapterPostgres(db),
                identity=SimpleNamespace(providers=providers),
            )
            return await OidcSignInService.route(service, email)

    assert asyncio.run(route("someone@gmail.com")) == "default-idp"
    assert asyncio.run(route("someone@corp.example")) == "corp-sso"


def test_a_domain_in_another_case_is_the_same_domain(world, nexus_db) -> None:
    first = world.org("pat", "pat")
    second = world.org("olivia", "olivia")
    _legacy_domains(nexus_db, ("Verified.example", first, True), ("Pending.example", first, False))
    http = world.as_("olivia")
    taken = http.post(f"/organizations/{second}/domains", json={"domain": "verified.example"})
    assert taken.status_code == 400
    moved = http.post(f"/organizations/{second}/domains", json={"domain": "pending.example"})
    assert moved.status_code == 200, moved.text
    assert moved.json()["id"] == "legacy-1"
    assert world.as_("pat").get(f"/organizations/{first}/domains").json()[0]["domain"] == (
        "Verified.example"
    )

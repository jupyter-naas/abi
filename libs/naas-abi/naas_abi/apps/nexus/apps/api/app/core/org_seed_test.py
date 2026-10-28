from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from naas_abi.apps.nexus.apps.api.app.core import org_seed
from naas_abi.apps.nexus.apps.api.app.core.config import UserSeedConfig, WorkspaceSeedConfig

ADMIN = "admin@example.com"


@pytest.fixture
def seed_admin(monkeypatch: pytest.MonkeyPatch):
    def run(existing_user, *, is_superadmin: bool = True):
        async def lookup(_session, _email):
            return existing_user

        monkeypatch.setattr(org_seed, "_get_user_by_email", lookup)
        monkeypatch.setattr(
            org_seed.settings,
            "users",
            [UserSeedConfig(email=ADMIN, name="Admin", is_superadmin=is_superadmin)],
        )
        session = MagicMock()
        asyncio.run(org_seed._upsert_users(session=session))
        return session

    return run


def test_a_new_configured_user_is_made_with_no_password(seed_admin) -> None:
    session = seed_admin(None)

    created = session.add.call_args.args[0]
    assert (created.email, created.name, created.is_superadmin) == (ADMIN, "Admin", True)
    assert created.id.startswith("user-")
    # They sign in at the built-in identity provider, which links this account at
    # the first sign-in: nothing here holds a credential.
    assert not hasattr(created, "hashed_password")
    assert created.principal_id is None and created.idp_issuer is None


def test_the_store_credentials_setting_of_older_configurations_is_ignored() -> None:
    cfg = UserSeedConfig(
        email=ADMIN,
        name="Admin",
        store_credentials_in_secrets=False,  # type: ignore[call-arg]
    )
    assert not hasattr(cfg, "store_credentials_in_secrets")


def test_an_existing_user_is_left_alone_but_for_the_superadmin_flag(seed_admin) -> None:
    user = SimpleNamespace(
        is_superadmin=False, name="Kept", email=ADMIN, updated_at=None, organization="Acme"
    )

    seed_admin(user, is_superadmin=True)

    assert (user.is_superadmin, user.name, user.organization) == (True, "Kept", "Acme")


def test_reseed_keeps_a_wallpaper_the_config_does_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = "/api/workspaces/ws-1/background-image?v=abc.png"
    workspace = SimpleNamespace(
        id="ws-1",
        owner_id="user-1",
        organization_id="org-1",
        background_image_url=saved,
        primary_color="#000000",
        updated_at=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    owner = SimpleNamespace(id="user-1")

    async def owner_lookup(*_args, **_kwargs):
        return owner

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(org_seed, "_resolve_user", owner_lookup)
    monkeypatch.setattr(org_seed, "_get_user_by_id", owner_lookup)
    monkeypatch.setattr(org_seed, "_ensure_workspace_member", noop)
    monkeypatch.setattr(org_seed, "_seed_workspace_apps", noop)

    cfg = WorkspaceSeedConfig(
        name="Forvis Mazars France",
        slug="forvis-mazars-france",
        owner_email=ADMIN,
        primary_color="#0057B8",
    )

    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    assert workspace.background_image_url == saved
    # Bootstrap only: the colour already on the workspace wins over the config.
    assert workspace.primary_color == "#000000"


def test_reseed_keeps_a_wallpaper_set_in_the_app_over_the_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = SimpleNamespace(
        id="ws-1",
        owner_id="user-1",
        organization_id="org-1",
        background_image_url="/api/workspaces/ws-1/background-image?v=custom.png",
        updated_at=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    owner = SimpleNamespace(id="user-1")

    async def owner_lookup(*_args, **_kwargs):
        return owner

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(org_seed, "_resolve_user", owner_lookup)
    monkeypatch.setattr(org_seed, "_get_user_by_id", owner_lookup)
    monkeypatch.setattr(org_seed, "_ensure_workspace_member", noop)
    monkeypatch.setattr(org_seed, "_seed_workspace_apps", noop)

    seeded = "src/external/valeo/assets/public/cover.webp"
    cfg = WorkspaceSeedConfig(
        name="Valeo",
        slug="valeo",
        owner_email=ADMIN,
        background_image_url=seeded,
    )

    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    assert workspace.background_image_url == "/api/workspaces/ws-1/background-image?v=custom.png"


def test_config_superadmins_become_iam_platform_admins(monkeypatch: pytest.MonkeyPatch) -> None:
    from naas_abi_core.engine.call_context import (
        CallContext,
        Principal,
        as_service_account,
        use_call_context,
    )
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
    from naas_abi_core.services.iam.IAMService import IAMService

    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    users = [
        UserSeedConfig(email=ADMIN, name="Admin", is_superadmin=True),
        UserSeedConfig(email="bob@example.com", name="Bob"),
    ]
    monkeypatch.setattr(org_seed, "settings", SimpleNamespace(users=users))
    rows = {
        ADMIN: SimpleNamespace(id="user-aaaaaaaaaaaa", email=ADMIN, name="Admin"),
        "bob@example.com": SimpleNamespace(
            id="user-bbbbbbbbbbbb", email="bob@example.com", name="Bob"
        ),
    }

    def allowed(nexus_user_id: str) -> bool:
        # A Nexus request: api on behalf of the signed-in user.
        ctx = CallContext(
            principal=Principal(id="api", kind="service_account", name="api"),
            on_behalf_of=Principal(id=nexus_user_id, kind="user"),
        )
        with use_call_context(ctx):
            # Outside the grants a plain Nexus user holds.
            return iam.authorize("nexus:ManageSystem", "abi:-:-:nexus:system/-").allowed

    with as_service_account("api"):
        org_seed.sync_platform_admins(iam, rows)
    assert allowed("user-aaaaaaaaaaaa")
    assert not allowed("user-bbbbbbbbbbbb")

    # Left out of the config: the platform administrator stays one (the
    # configuration only promotes; demoting is Admin > Users).
    users[0] = UserSeedConfig(email=ADMIN, name="Admin", is_superadmin=False)
    with as_service_account("api"):
        org_seed.sync_platform_admins(iam, rows)
    assert allowed("user-aaaaaaaaaaaa")


def test_a_linked_users_profile_is_not_written_back_by_the_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
    from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER, IAMService

    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    monkeypatch.setattr(
        org_seed,
        "settings",
        SimpleNamespace(users=[UserSeedConfig(email=ADMIN, name="Admin", is_superadmin=True)]),
    )
    with as_service_account("engine"):
        legacy = iam.ensure_user(LEGACY_NEXUS_ISSUER, "user-aaaaaaaaaaaa", provider="nexus")
        iam.link_user(
            legacy.id,
            "https://idp.example",
            "sub-1",
            provider="builtin",
            email=ADMIN,
            email_verified=True,
        )
    rows = {ADMIN: SimpleNamespace(id="user-aaaaaaaaaaaa", email=ADMIN, name="Admin")}

    with as_service_account("api"):
        org_seed.sync_platform_admins(iam, rows)

    record = iam.store.get_principal(legacy.id)
    assert (record.provider, record.email, record.email_verified) == ("builtin", ADMIN, True)


# -- the configured users at the built-in identity provider -----------------------------------


class FakeIdentity:
    def __init__(self, *, provisioning: str = "builtin", down: int = 0) -> None:
        self.provisioning = provisioning
        self.down = down
        self.calls: list[tuple[str, str, str | None, str]] = []

    def list_providers(self):
        return [SimpleNamespace(name="builtin", provisioning=self.provisioning)]

    def provision_user(self, provider, email, *, name=None):
        from naas_abi_core.engine.call_context import current_call_context
        from naas_abi_core.services.identity.IdentityPorts import ProviderUnavailableError

        if self.down > 0:
            self.down -= 1
            raise ProviderUnavailableError("the built-in identity provider is not reachable yet")
        self.calls.append((provider, email, name, current_call_context().principal.id))
        return SimpleNamespace(created=True)


def test_the_configured_users_are_made_at_the_built_in_provider_as_nexus() -> None:
    identity = FakeIdentity()

    done = org_seed.provision_seed_users(identity, [(ADMIN, "Admin"), ("bob@example.com", "Bob")])

    assert done == [ADMIN, "bob@example.com"]
    assert identity.calls == [
        ("builtin", ADMIN, "Admin", "api"),
        ("builtin", "bob@example.com", "Bob", "api"),
    ]


@pytest.mark.parametrize("provisioning", ["none", "zitadel", "keycloak"])
def test_only_the_built_in_provider_is_asked_to_make_people(provisioning: str) -> None:
    identity = FakeIdentity(provisioning=provisioning)

    assert org_seed.provision_seed_users(identity, [(ADMIN, "Admin")]) == []
    assert identity.calls == []


def test_the_seed_waits_for_the_provider_module_to_come_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(org_seed, "_PROVISION_RETRY_SECONDS", 0.0)
    identity = FakeIdentity(down=3)

    asyncio.run(org_seed._provision_when_ready(identity, [(ADMIN, "Admin")]))

    assert [call[1] for call in identity.calls] == [ADMIN]


def test_a_provider_that_never_comes_up_never_stops_the_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(org_seed, "_PROVISION_RETRY_SECONDS", 0.0)
    monkeypatch.setattr(org_seed, "_PROVISION_ATTEMPTS", 3)
    identity = FakeIdentity(down=99)

    asyncio.run(org_seed._provision_when_ready(identity, [(ADMIN, "Admin")]))

    assert identity.calls == []


def test_a_failure_of_the_provider_is_logged_not_raised() -> None:
    class Broken(FakeIdentity):
        def provision_user(self, provider, email, *, name=None):
            raise RuntimeError("the provider refused this address")

    asyncio.run(org_seed._provision_when_ready(Broken(), [(ADMIN, "Admin")]))


@pytest.fixture
def seed_users(monkeypatch: pytest.MonkeyPatch):
    def run(existing_user, users: list[UserSeedConfig]):
        async def lookup(_session, _email):
            return existing_user

        monkeypatch.setattr(org_seed, "_get_user_by_email", lookup)
        monkeypatch.setattr(org_seed.settings, "users", users)
        asyncio.run(org_seed._upsert_users(session=MagicMock()))

    return run


def test_config_promotes_an_existing_user_to_superadmin(seed_users) -> None:
    user = SimpleNamespace(is_superadmin=False, updated_at=None)

    seed_users(user, [UserSeedConfig(email=ADMIN, name="Admin", is_superadmin=True)])

    assert user.is_superadmin is True


def test_config_never_demotes_a_superadmin_promoted_in_the_platform(seed_users) -> None:
    user = SimpleNamespace(is_superadmin=True, updated_at=None)

    seed_users(user, [UserSeedConfig(email=ADMIN, name="Admin", is_superadmin=False)])

    assert user.is_superadmin is True


def _patch_member_helpers(monkeypatch: pytest.MonkeyPatch, owner) -> list[tuple]:
    ensured: list[tuple] = []

    async def owner_lookup(*_args, **_kwargs):
        return owner

    async def record_ws_member(_session, workspace_id, user_id, role, organization_id=None):
        ensured.append(("workspace", workspace_id, user_id, role))

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(org_seed, "_resolve_user", owner_lookup)
    monkeypatch.setattr(org_seed, "_get_user_by_id", owner_lookup)
    monkeypatch.setattr(org_seed, "_ensure_workspace_member", record_ws_member)
    monkeypatch.setattr(org_seed, "_seed_workspace_apps", noop)
    return ensured


def test_workspace_seed_only_ensures_the_owner_and_ignores_members(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    workspace = SimpleNamespace(
        id="ws-1", owner_id="user-1", organization_id="org-1", updated_at=None
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    ensured = _patch_member_helpers(monkeypatch, SimpleNamespace(id="user-1"))
    cfg = WorkspaceSeedConfig(
        name="Valeo",
        slug="valeo",
        owner_email=ADMIN,
        members=[{"email": "someone@example.com", "role": "admin"}],
    )

    with caplog.at_level("WARNING"):
        asyncio.run(
            org_seed._upsert_workspace(
                session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
            )
        )

    assert ensured == [("workspace", "ws-1", "user-1", "owner")]
    assert "members" in caplog.text and "valeo" in caplog.text


@pytest.mark.parametrize(
    ("current", "expected"),
    [(None, "Key Accounts"), ("", "Key Accounts"), ("Renamed in the UI", "Renamed in the UI")],
)
def test_reseed_sets_the_group_only_when_the_workspace_has_none(
    monkeypatch: pytest.MonkeyPatch, current: str | None, expected: str
) -> None:
    workspace = SimpleNamespace(
        id="ws-1",
        owner_id="user-1",
        organization_id="org-1",
        background_image_url=None,
        workspace_group=current,
        updated_at=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    owner = SimpleNamespace(id="user-1")

    async def owner_lookup(*_args, **_kwargs):
        return owner

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(org_seed, "_resolve_user", owner_lookup)
    monkeypatch.setattr(org_seed, "_get_user_by_id", owner_lookup)
    monkeypatch.setattr(org_seed, "_ensure_workspace_member", noop)
    monkeypatch.setattr(org_seed, "_seed_workspace_apps", noop)

    cfg = WorkspaceSeedConfig(name="Orange", slug="orange", owner_email=ADMIN, group="Key Accounts")
    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    assert workspace.workspace_group == expected


def test_reseed_keeps_name_logo_and_colours_set_in_the_ui(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = SimpleNamespace(
        id="ws-1",
        owner_id="user-1",
        organization_id="org-1",
        name="Orange (renamed in the UI)",
        logo_url="/api/workspaces/ws-1/logo",
        logo_emoji=None,
        primary_color="#123456",
        accent_color=None,
        background_color=None,
        background_image_url=None,
        sidebar_color=None,
        font_family=None,
        workspace_group=None,
        updated_at=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    _patch_member_helpers(monkeypatch, SimpleNamespace(id="user-1"))
    cfg = WorkspaceSeedConfig(
        name="Orange",
        slug="orange",
        owner_email=ADMIN,
        logo_url="https://example.com/orange.png",
        primary_color="#22c55e",
        accent_color="#ff7900",
    )

    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    # Values already on the workspace win; the seed only fills empty ones.
    assert workspace.name == "Orange (renamed in the UI)"
    assert workspace.logo_url == "/api/workspaces/ws-1/logo"
    assert workspace.primary_color == "#123456"
    assert workspace.accent_color == "#ff7900"
    assert workspace.background_image_url is None


def test_reseed_keeps_the_workspace_owner_and_organization_set_in_the_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = SimpleNamespace(
        id="ws-1",
        owner_id="user-2",
        organization_id="org-2",
        background_image_url=None,
        workspace_group=None,
        updated_at=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    ensured = _patch_member_helpers(monkeypatch, SimpleNamespace(id="user-1"))
    cfg = WorkspaceSeedConfig(name="Valeo", slug="valeo", owner_email=ADMIN)

    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    assert (workspace.owner_id, workspace.organization_id) == ("user-2", "org-2")
    # The owner membership follows the workspace's actual owner, not the config.
    assert ensured == [("workspace", "ws-1", "user-2", "owner")]


def test_reseed_fills_a_missing_workspace_owner_and_organization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = SimpleNamespace(
        id="ws-1",
        owner_id=None,
        organization_id=None,
        background_image_url=None,
        workspace_group=None,
        updated_at=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=workspace))
    )
    ensured = _patch_member_helpers(monkeypatch, SimpleNamespace(id="user-1"))
    cfg = WorkspaceSeedConfig(name="Valeo", slug="valeo", owner_email=ADMIN)

    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    assert (workspace.owner_id, workspace.organization_id) == ("user-1", "org-1")
    assert ensured == [("workspace", "ws-1", "user-1", "owner")]


def test_a_workspace_seeded_without_a_name_is_named_after_its_slug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    _patch_member_helpers(monkeypatch, SimpleNamespace(id="user-1"))
    cfg = WorkspaceSeedConfig(slug="valeo", apps=["naas_abi.apps:example"])

    asyncio.run(
        org_seed._upsert_workspace(
            session, cfg, SimpleNamespace(id="org-1", owner_id="user-1", slug="forvis"), {}
        )
    )

    created = session.add.call_args.args[0]
    assert (created.slug, created.name, created.owner_id) == ("valeo", "valeo", "user-1")

"""The people service with fakes: the order of a creation (authorized before the
provider is asked), the take-back of a creation that fails after it, linking an
email that has an account, ``provisioning: none``, levels and groups (#1589), search,
resend, activation."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    ADMINS,
    CAPABILITY,
    MEMBERSHIP,
    AccessGateway,
    AlreadyActiveError,
    AlreadyMemberError,
    EmailTakenError,
    Grant,
    GrantNotHeldError,
    IdentityGateway,
    LastOrgAdminError,
    NewUser,
    NoProviderError,
    PeopleMailer,
    PeopleStorePort,
    Placement,
    PlatformUser,
    ProviderInfo,
    Provisioned,
    ProvisioningFailedError,
    ProvisioningRefused,
    Seat,
    UnknownUserError,
    UserStatus,
    WorkspaceAccess,
)
from naas_abi.apps.nexus.apps.api.app.services.people.service import UNBOUND_PREFIX, PeopleService

NOW = datetime(2026, 11, 19, 12, 0)
BUILTIN = ProviderInfo("builtin", "Built-in", "https://idp", "builtin")
CORP = ProviderInfo("corp", "Corp SSO", "https://corp", "none")
WS_SCOPE = workspace_container("org-1", "ws-1")
WS2_SCOPE = workspace_container("org-1", "ws-2")
ORG_SCOPE = org_container("org-1")
ADMIN = SimpleNamespace(id="admin", name="Ada")
WS = Grant("org-1", workspaces=(WorkspaceAccess("ws-1"),))
ORG = Grant("org-1", org_admin=True)
RUNNERS = "grp_runners"


class Store(PeopleStorePort):
    def __init__(self) -> None:
        self.rows: dict[str, PlatformUser] = {}
        self.uncommitted: dict[str, PlatformUser] = {}
        self.provisioned: set[tuple[str, str]] = set()
        self.profiles: dict[tuple[str, str], dict[str, str]] = {}
        self.taken_on_add: str | None = None
        self.log: list[str] = []

    async def get(self, user_id):
        return self.rows.get(user_id)

    async def by_email(self, email):
        return next((u for u in self.rows.values() if u.email == email), None)

    async def search(self, q, among: Collection[str], limit):
        found = [
            u
            for u in self.rows.values()
            if u.id in among and (q.lower() in (u.name or "").lower() or q.lower() in u.email)
        ]
        return sorted(found, key=lambda u: u.name or "")[:limit]

    async def add(self, user: NewUser, *, now):
        if self.taken_on_add is not None:
            self.rows[self.taken_on_add] = PlatformUser(
                self.taken_on_add, user.email, "Raced", UserStatus.ACTIVE, user.provider
            )
            raise EmailTakenError(user.email)
        self.log.append("row")
        row = PlatformUser(user.id, user.email, user.name, UserStatus.INVITED, user.provider)
        self.uncommitted[user.id] = row
        self.bound = (user.principal_id, user.issuer, user.subject)
        return row

    async def remove(self, user_id):
        self.log.append("remove row")
        self.rows.pop(user_id, None)

    async def activate(self, user_id, *, now):
        row = self.rows.get(user_id)
        if row is None or row.status != UserStatus.INVITED:
            return False
        self.rows[user_id] = replace(row, status=UserStatus.ACTIVE)
        return True

    async def write_profile(self, organization_id, user_id, profile: Mapping[str, str]):
        self.profiles[(organization_id, user_id)] = dict(profile)

    async def record_provisioned(self, provider, subject, email, *, now):
        self.provisioned.add((provider, subject))

    async def forget_provisioned(self, provider, subject):
        self.provisioned.discard((provider, subject))

    async def provider_for_domain(self, domain, organization_id):
        return "corp" if domain == "corp.example" and organization_id else None

    async def names(self, organization_id, workspace_id):
        return (
            {"org-1": "Acme"}.get(organization_id or ""),
            {"ws-1": "Research", "ws-2": "Sales"}.get(workspace_id or ""),
        )

    async def commit(self):
        self.rows.update(self.uncommitted)
        self.uncommitted.clear()

    async def rollback(self):
        self.uncommitted.clear()


class Idp(IdentityGateway):
    def __init__(self, *providers: ProviderInfo, default: str | None = "builtin") -> None:
        self.known = list(providers or (BUILTIN,))
        self.default = default
        self.accounts: dict[str, str] = {}
        self.fails: Exception | None = None
        self.refuses_user = False
        self.calls: list[tuple[str, str | None]] = []
        self.deleted: list[str] = []
        self.log: list[str] | None = None

    async def providers(self):
        return list(self.known), self.default

    async def provision(self, provider, email, name, *, by=None):
        self.calls.append((email, by))
        if self.log is not None:
            self.log.append("provision")
        if provider.managed_in_provider:
            return None
        if by is not None and self.refuses_user:
            raise ProvisioningRefused("no identity:ProvisionUser")
        if self.fails is not None:
            raise self.fails
        created = email not in self.accounts
        self.accounts.setdefault(email, f"sub-{email.split('@')[0]}")
        return Provisioned(subject=self.accounts[email], created=created)

    async def delete(self, provider, subject):
        self.deleted.append(subject)
        self.accounts = {e: s for e, s in self.accounts.items() if s != subject}


class Access(AccessGateway):
    """IAM as groups and a level. ``may`` is the seats each caller may put someone
    in (or take them out of); ``level_changers`` who may change a level. Every join,
    leave and level change is recorded with who asked (``audit``)."""

    def __init__(self) -> None:
        self.may: dict[str, set[Seat]] = {
            "admin": {
                Seat(WS_SCOPE, MEMBERSHIP),
                Seat(WS2_SCOPE, MEMBERSHIP),
                Seat(WS2_SCOPE, ADMINS),
                Seat(ORG_SCOPE, MEMBERSHIP),
                Seat(ORG_SCOPE, ADMINS),
                Seat(ORG_SCOPE, CAPABILITY, RUNNERS),
            },
            "wsadmin": {Seat(WS_SCOPE, MEMBERSHIP), Seat(WS_SCOPE, ADMINS)},
        }
        self.level_changers = {"admin", "wsadmin"}
        self.seats: dict[str, set[Seat]] = {}
        self.levels: dict[str, str] = {}
        self.principals: dict[tuple[str, str], str] = {}
        self.discarded: list[str] = []
        self.fail_join: Exception | None = None
        self.log: list[str] | None = None
        self.audit: list[tuple[str, str, object, str | None]] = []

    async def container(self, kind, id):
        if id == "nope":
            raise LookupError(id)
        if kind == "organization":
            return org_container(id)
        return workspace_container("org-1", id)

    def _require(self, seats: Sequence[Seat], by: str) -> None:
        for seat in seats:
            if seat not in self.may.get(by, set()):
                raise GrantNotHeldError(f"{by} may not put anyone in {seat}")

    async def check(self, user_id, seats, *, level, by, organization_id):
        if self.log is not None:
            self.log.append("check")
        for seat in seats:
            if seat.kind == CAPABILITY and seat.group_id != RUNNERS:
                raise ValueError(f"Not a capability group here: {seat.group_id}")
        self._require(seats, by)
        if level is not None and by not in self.level_changers:
            raise GrantNotHeldError(f"{by} may not change a level")

    async def held(self, user_id, seats):
        return {s for s in seats if s in self.seats.get(user_id, set())}

    async def level_of(self, user_id):
        return self.levels.get(user_id)

    async def join(self, user_id, seat, *, by, level):
        if self.fail_join is not None and seat.kind != MEMBERSHIP:
            raise self.fail_join
        mine = self.seats.setdefault(user_id, set())
        if seat in mine:
            return False
        mine.add(seat)
        self.audit.append(("join", user_id, seat, by))
        return True

    async def leave(self, user_id, seat, *, by):
        mine = self.seats.get(user_id, set())
        if seat not in mine:
            return False
        if seat.kind == ADMINS and seat.container == ORG_SCOPE:
            if not any(seat in s for u, s in self.seats.items() if u != user_id):
                raise LastOrgAdminError(seat.container)
        mine.discard(seat)
        self.audit.append(("leave", user_id, seat, by))
        return True

    async def check_leaving(self, user_id, seats, *, by):
        self._require(seats, by)
        for seat in seats:
            if seat.kind == ADMINS and seat.container == ORG_SCOPE:
                if not any(seat in s for u, s in self.seats.items() if u != user_id):
                    raise LastOrgAdminError(seat.container)

    async def set_level(self, user_id, level, *, by, where=()):
        if by is not None and by not in self.level_changers:
            raise GrantNotHeldError(f"{by} may not change a level")
        before = self.levels.get(user_id)
        self.levels[user_id] = level
        self.audit.append(("level", user_id, level, by))
        return before

    async def clear_level(self, user_id):
        self.levels.pop(user_id, None)

    async def capability_groups(self, organization_id):
        return [(RUNNERS, "Workflow runners")]

    async def ensure_principal(self, issuer, subject, *, provider, email, name):
        return self.principals.setdefault((issuer, subject), f"usr_{subject}")

    async def discard_principal(self, principal_id):
        self.discarded.append(principal_id)

    async def roles_of(self, user_id):
        found: dict[str, str] = {}
        for seat in self.seats.get(user_id, set()):
            if seat.kind == CAPABILITY:
                continue
            if seat.kind == ADMINS:
                found[seat.container] = "admin"
            else:
                found.setdefault(seat.container, self.levels.get(user_id, "viewer"))
        return found


class Mailer(PeopleMailer):
    def __init__(self) -> None:
        self.invitations: list[tuple[str, str, Placement, bool]] = []
        self.notices: list[tuple[str, Placement]] = []

    async def invitation(self, *, to_email, provider, inviter_name, placement, account_made):
        self.invitations.append((to_email, provider.name, placement, account_made))
        return True

    async def added(self, *, to_email, inviter_name, placement):
        self.notices.append((to_email, placement))
        return True


@pytest.fixture
def world():
    store, idp, access, mailer = Store(), Idp(BUILTIN, CORP), Access(), Mailer()
    service = PeopleService(store, idp, access, mailer, clock=lambda: NOW)
    return SimpleNamespace(service=service, store=store, idp=idp, access=access, mailer=mailer)


async def _create(world, email="bob@example.com", grant=WS, **kwargs):
    return await world.service.create_or_link(
        email=email,
        name=kwargs.pop("name", "Bob"),
        provider=kwargs.pop("provider", None),
        grant=grant,
        by=kwargs.pop("by", ADMIN),
        **kwargs,
    )


def _active(world, user_id: str) -> None:
    world.store.rows[user_id] = PlatformUser(
        user_id, f"{user_id}@example.com", user_id.title(), UserStatus.ACTIVE, "builtin"
    )


# -- creating ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_new_email_is_a_bound_invited_user_in_its_groups_before_any_sign_in(world):
    result = await _create(
        world,
        email=" Bob@Example.com ",
        organization_id="org-1",
        profile={"job_title": "Analyst", "unknown": "x"},
    )

    user = result.user
    assert user.id == "usr_sub-bob" and user.email == "bob@example.com"
    assert user.status == UserStatus.INVITED and user.provider == "builtin"
    assert world.store.rows[user.id] == user
    assert world.store.bound == ("usr_sub-bob", "https://idp", "sub-bob")
    # Joined the workspace's group; someone with no level who joins a workspace is a Member.
    assert world.access.seats[user.id] == {Seat(WS_SCOPE, MEMBERSHIP)}
    assert world.access.levels[user.id] == "member"
    assert world.store.provisioned == {("builtin", "sub-bob")}
    assert world.store.profiles == {("org-1", user.id): {"job_title": "Analyst"}}
    assert result.created and result.provisioned and result.sign_in_email_sent
    assert world.mailer.invitations == [
        ("bob@example.com", "builtin", Placement("Acme", None, "Research", "member"), True)
    ]


@pytest.mark.asyncio
async def test_create_at_org_level_with_two_workspaces_admin_of_one_and_a_capability(world):
    grant = Grant(
        "org-1",
        level="member",
        workspaces=(WorkspaceAccess("ws-1"), WorkspaceAccess("ws-2", admin=True)),
        capabilities=(RUNNERS,),
    )
    user = (await _create(world, grant=grant)).user

    assert world.access.seats[user.id] == {
        Seat(WS_SCOPE, MEMBERSHIP),
        Seat(WS2_SCOPE, MEMBERSHIP),
        Seat(WS2_SCOPE, ADMINS),
        Seat(ORG_SCOPE, CAPABILITY, RUNNERS),
    }
    assert world.access.levels[user.id] == "member"
    # Not in "<O> people": their workspaces tie them to the organization.
    assert Seat(ORG_SCOPE, MEMBERSHIP) not in world.access.seats[user.id]


@pytest.mark.asyncio
async def test_an_org_only_person_joins_the_organizations_people(world):
    user = (await _create(world, grant=Grant("org-1", level="viewer"))).user
    assert world.access.seats[user.id] == {Seat(ORG_SCOPE, MEMBERSHIP)}
    assert world.access.levels[user.id] == "viewer"


@pytest.mark.asyncio
async def test_an_org_admin_joins_the_people_and_the_admins(world):
    user = (await _create(world, grant=ORG)).user
    assert world.access.seats[user.id] == {Seat(ORG_SCOPE, MEMBERSHIP), Seat(ORG_SCOPE, ADMINS)}


@pytest.mark.asyncio
async def test_authorization_runs_before_the_provider_is_asked(world):
    log: list[str] = []
    world.access.log = world.idp.log = log
    await _create(world)
    assert log[:2] == ["check", "provision"]

    world.idp.calls.clear()
    with pytest.raises(GrantNotHeldError):
        await _create(
            world,
            email="eve@example.com",
            grant=Grant("org-1", workspaces=(WorkspaceAccess("ws-1", admin=True),)),
            by=SimpleNamespace(id="member", name="M"),
        )
    assert world.idp.calls == []  # nobody was made at the provider
    assert await world.service.by_email("eve@example.com") is None


@pytest.mark.asyncio
async def test_a_grant_is_checked_before_anything_is_asked(world):
    for bad in (
        Grant("org-1", level="owner"),  # type: ignore[arg-type]
        Grant("org-1", level="viewer", workspaces=(WorkspaceAccess("ws-1", admin=True),)),
        Grant("org-1", workspaces=(WorkspaceAccess("nope"),)),
        Grant(None, org_admin=True),
        Grant(None),
        Grant("org-1", capabilities=("grp_unknown",)),
    ):
        with pytest.raises(ValueError):
            await _create(world, grant=bad)
    assert world.idp.calls == [] and world.store.rows == {}


@pytest.mark.asyncio
async def test_a_failure_after_provisioning_takes_everything_back(world):
    world.access.fail_join = RuntimeError("IAM went away")
    grant = Grant("org-1", workspaces=(WorkspaceAccess("ws-2", admin=True),))
    with pytest.raises(RuntimeError):
        await _create(world, grant=grant)

    assert world.idp.deleted == ["sub-bob"]  # the account this call made
    assert world.access.discarded == ["usr_sub-bob"]
    assert world.store.rows == {} and world.store.provisioned == set()
    # All or nothing: the membership joined first and the level are taken back.
    assert world.access.seats.get("usr_sub-bob", set()) == set()
    assert "usr_sub-bob" not in world.access.levels
    assert world.mailer.invitations == []


@pytest.mark.asyncio
async def test_an_account_the_provider_had_already_is_never_deleted_on_a_failure(world):
    world.idp.accounts["bob@example.com"] = "sub-old"
    world.access.fail_join = RuntimeError("IAM went away")
    with pytest.raises(RuntimeError):
        await _create(world, grant=Grant("org-1", workspaces=(WorkspaceAccess("ws-2", True),)))
    assert world.idp.deleted == [] and world.access.discarded == []
    assert world.store.rows == {}


@pytest.mark.asyncio
async def test_a_provider_failure_makes_nothing(world):
    world.idp.fails = ProvisioningFailedError("the provider is down")
    with pytest.raises(ProvisioningFailedError):
        await _create(world)
    assert world.store.rows == {} and world.access.seats == {}


@pytest.mark.asyncio
async def test_no_provider_is_a_no_provider_error(world):
    world.idp.known = []
    with pytest.raises(NoProviderError):
        await _create(world)
    with pytest.raises(NoProviderError):
        await _create(world, provider="ghost")


# -- linking -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_email_with_an_account_is_linked_never_duplicated(world):
    world.store.rows["carl"] = PlatformUser(
        "carl", "carl@example.com", "Carl", UserStatus.ACTIVE, "x"
    )
    world.access.levels["carl"] = "viewer"

    result = await _create(world, email="Carl@example.com")

    assert result.user.id == "carl" and not result.created and not result.provisioned
    assert list(world.store.rows) == ["carl"] and world.idp.calls == []
    assert world.access.seats["carl"] == {Seat(WS_SCOPE, MEMBERSHIP)}
    # No level asked: theirs stays.
    assert world.access.levels["carl"] == "viewer"
    assert world.mailer.notices == [
        ("carl@example.com", Placement("Acme", None, "Research", "member"))
    ]
    assert world.mailer.invitations == []


@pytest.mark.asyncio
async def test_linking_an_invited_person_sends_the_invitation_again(world):
    first = await _create(world)
    world.mailer.invitations.clear()

    again = await _create(world, grant=ORG)

    assert again.user.id == first.user.id and not again.created
    assert world.access.seats[first.user.id] == {
        Seat(WS_SCOPE, MEMBERSHIP),
        Seat(ORG_SCOPE, MEMBERSHIP),
        Seat(ORG_SCOPE, ADMINS),
    }
    assert [m[0] for m in world.mailer.invitations] == ["bob@example.com"]


@pytest.mark.asyncio
async def test_a_workspace_already_joined_is_already_member(world):
    _active(world, "carl")
    world.access.seats["carl"] = {Seat(WS_SCOPE, MEMBERSHIP)}
    with pytest.raises(AlreadyMemberError):
        await _create(world, email="carl@example.com")
    assert world.access.seats["carl"] == {Seat(WS_SCOPE, MEMBERSHIP)}


@pytest.mark.asyncio
async def test_a_row_made_meanwhile_is_linked(world):
    world.store.taken_on_add = "raced"
    result = await _create(world)
    assert result.user.id == "raced" and not result.created
    assert world.access.seats["raced"] == {Seat(WS_SCOPE, MEMBERSHIP)}
    assert world.idp.deleted == []  # the provider's account is that person's
    # ABI made it, whoever's row it is bound to: recorded as ABI's.
    assert world.store.provisioned == {("builtin", "sub-bob")}


@pytest.mark.asyncio
async def test_someone_who_signed_in_under_another_email_is_linked_not_duplicated(world):
    """The provider has their account, its IAM user has a row (an unverified email at
    their first sign-in, or one changed since): that row is the person."""
    world.idp.accounts["bob@example.com"] = "sub-bob"
    world.store.rows["usr_sub-bob"] = PlatformUser(
        "usr_sub-bob", "usr_sub-bob@unverified.internal", "Bob", UserStatus.ACTIVE, "builtin"
    )

    result = await _create(world, organization_id="org-1", profile={"job_title": "CFO"})

    assert result.user.id == "usr_sub-bob" and not result.created
    assert list(world.store.rows) == ["usr_sub-bob"]
    assert world.access.seats["usr_sub-bob"] == {Seat(WS_SCOPE, MEMBERSHIP)}
    assert world.idp.deleted == []
    # A workspace grant alone never rewrites an existing person's organization profile.
    assert world.store.profiles == {}


@pytest.mark.asyncio
async def test_a_workspace_admin_linking_someone_leaves_their_org_profile_alone(world):
    _active(world, "alice")
    world.store.profiles[("org-1", "alice")] = {"job_title": "CFO"}

    result = await _create(
        world, email="alice@example.com", organization_id="org-1", profile={"job_title": "Intern"}
    )

    assert result.user.id == "alice" and not result.created
    assert world.store.profiles == {("org-1", "alice"): {"job_title": "CFO"}}


@pytest.mark.asyncio
async def test_an_org_grant_on_a_link_writes_the_profile(world):
    _active(world, "alice")
    await _create(
        world,
        email="alice@example.com",
        grant=ORG,
        organization_id="org-1",
        profile={"job_title": "CFO"},
    )
    assert world.store.profiles == {("org-1", "alice"): {"job_title": "CFO"}}


@pytest.mark.asyncio
async def test_linking_with_no_grant_writes_no_profile(world):
    _active(world, "carl")
    await _create(
        world, email="carl@example.com", grant=None, organization_id="org-1", profile={"bio": "x"}
    )
    assert world.store.profiles == {}


# -- provisioning: none, and a platform invitation without the right -----------------------


@pytest.mark.asyncio
async def test_a_provider_that_manages_its_people_makes_an_unbound_invited_row(world):
    world.access.log = []
    result = await _create(world, email="dan@corp.example", organization_id="org-1")

    user = result.user
    assert user.id.startswith(UNBOUND_PREFIX) and user.provider == "corp"
    assert world.store.bound == (None, None, None)
    assert world.access.seats[user.id] == {Seat(WS_SCOPE, MEMBERSHIP)}
    # Checked before the row exists, then again for the person made.
    assert world.access.log == ["check", "check"]
    assert not result.provisioned
    assert world.mailer.invitations[0][1] == "corp"


@pytest.mark.asyncio
async def test_a_platform_invitation_is_made_on_the_inviters_own_right(world):
    result = await _create(world, grant=None)
    assert world.idp.calls == [("bob@example.com", "admin")]
    assert result.user.id == "usr_sub-bob" and not result.provisioning_skipped

    world.idp.refuses_user = True
    skipped = await _create(world, email="fay@example.com", grant=None)
    assert skipped.provisioning_skipped and skipped.user.id.startswith(UNBOUND_PREFIX)
    assert world.mailer.invitations[-1][3] is False  # the mail promises no code


# -- adding, changing a level, changing access ---------------------------------------------


@pytest.mark.asyncio
async def test_add_existing_joins_and_tells_them(world):
    _active(world, "carl")
    user = await world.service.add_existing(user_id="carl", grant=WS, by=ADMIN)
    assert user.id == "carl" and world.access.seats["carl"] == {Seat(WS_SCOPE, MEMBERSHIP)}
    assert len(world.mailer.notices) == 1
    assert isinstance(user, PlatformUser) and user.sign_in_email_sent is True

    with pytest.raises(AlreadyMemberError):
        await world.service.add_existing(user_id="carl", grant=WS, by=ADMIN)
    with pytest.raises(UnknownUserError):
        await world.service.add_existing(user_id="ghost", grant=WS, by=ADMIN)
    with pytest.raises(GrantNotHeldError):
        await world.service.add_existing(
            user_id="carl", grant=ORG, by=SimpleNamespace(id="wsadmin", name="W")
        )


@pytest.mark.asyncio
async def test_a_workspace_admin_of_one_of_their_workspaces_changes_a_level_audited(world):
    _active(world, "carl")
    world.access.levels["carl"] = "viewer"
    wsadmin = SimpleNamespace(id="wsadmin", name="W")

    before = await world.service.set_level(user_id="carl", level="member", by=wsadmin)

    assert before == "viewer" and world.access.levels["carl"] == "member"
    assert world.access.audit[-1] == ("level", "carl", "member", "wsadmin")


@pytest.mark.asyncio
async def test_a_plain_member_may_not_change_a_level(world):
    _active(world, "carl")
    world.access.levels["carl"] = "viewer"
    with pytest.raises(GrantNotHeldError):
        await world.service.set_level(
            user_id="carl", level="member", by=SimpleNamespace(id="member", name="M")
        )
    assert world.access.levels["carl"] == "viewer"
    with pytest.raises(ValueError):
        await world.service.set_level(user_id="carl", level="owner", by=ADMIN)
    with pytest.raises(UnknownUserError):
        await world.service.set_level(user_id="ghost", level="member", by=ADMIN)


@pytest.mark.asyncio
async def test_every_join_is_recorded_with_who_asked(world):
    user = (await _create(world, grant=ORG)).user
    asked = {(kind, by) for kind, uid, _what, by in world.access.audit if uid == user.id}
    assert asked == {("join", "admin")}


@pytest.mark.asyncio
async def test_change_access_moves_workspaces_admin_seats_and_capabilities(world):
    _active(world, "carl")
    world.access.seats["carl"] = {Seat(WS_SCOPE, MEMBERSHIP)}
    world.access.levels["carl"] = "member"

    await world.service.change_access(
        user_id="carl",
        organization_id="org-1",
        by=ADMIN,
        workspaces=[WorkspaceAccess("ws-2", admin=True)],
        among=["ws-1", "ws-2"],
        capabilities=[RUNNERS],
    )

    assert world.access.seats["carl"] == {
        Seat(WS2_SCOPE, MEMBERSHIP),
        Seat(WS2_SCOPE, ADMINS),
        Seat(ORG_SCOPE, CAPABILITY, RUNNERS),
    }

    # Out of every workspace: among the organization's people.
    world.access.may["admin"] |= {Seat(WS2_SCOPE, ADMINS)}
    await world.service.change_access(
        user_id="carl", organization_id="org-1", by=ADMIN, workspaces=[], among=["ws-1", "ws-2"]
    )
    assert Seat(ORG_SCOPE, MEMBERSHIP) in world.access.seats["carl"]
    assert Seat(WS2_SCOPE, MEMBERSHIP) not in world.access.seats["carl"]


@pytest.mark.asyncio
async def test_change_access_is_all_or_nothing(world):
    _active(world, "carl")
    world.access.seats["carl"] = {Seat(WS_SCOPE, MEMBERSHIP)}
    world.access.fail_join = RuntimeError("IAM went away")
    with pytest.raises(RuntimeError):
        await world.service.change_access(
            user_id="carl",
            organization_id="org-1",
            by=ADMIN,
            workspaces=[WorkspaceAccess("ws-1"), WorkspaceAccess("ws-2", admin=True)],
            among=["ws-1", "ws-2"],
        )
    assert world.access.seats["carl"] == {Seat(WS_SCOPE, MEMBERSHIP)}


@pytest.mark.asyncio
async def test_a_workspace_admin_makes_a_viewer_of_their_workspace_its_admin_and_back(world):
    _active(world, "carl")
    world.access.seats["carl"] = {Seat(WS_SCOPE, MEMBERSHIP)}
    world.access.levels["carl"] = "viewer"
    wsadmin = SimpleNamespace(id="wsadmin", name="W")

    await world.service.set_workspace_admin(
        user_id="carl", workspace_id="ws-1", admin=True, by=wsadmin
    )
    assert Seat(WS_SCOPE, ADMINS) in world.access.seats["carl"]
    assert world.access.levels["carl"] == "member"  # a workspace admin is a Member

    await world.service.set_workspace_admin(
        user_id="carl", workspace_id="ws-1", admin=False, by=wsadmin
    )
    assert world.access.seats["carl"] == {Seat(WS_SCOPE, MEMBERSHIP)}
    assert world.access.levels["carl"] == "member"
    with pytest.raises(UnknownUserError):  # not in that workspace
        await world.service.set_workspace_admin(
            user_id="carl", workspace_id="ws-2", admin=True, by=ADMIN
        )


@pytest.mark.asyncio
async def test_the_last_org_admin_keeps_the_seat(world):
    _active(world, "carl")
    world.access.seats["carl"] = {Seat(ORG_SCOPE, MEMBERSHIP), Seat(ORG_SCOPE, ADMINS)}
    with pytest.raises(LastOrgAdminError):
        await world.service.change_access(
            user_id="carl", organization_id="org-1", by=ADMIN, org_admin=False
        )
    assert Seat(ORG_SCOPE, ADMINS) in world.access.seats["carl"]


# -- search, resend, activation, provision -------------------------------------------------


@pytest.mark.asyncio
async def test_search_needs_two_characters_and_stays_among_the_ids_given(world):
    for i, (name, email) in enumerate(
        [("Florent", "florent@example.com"), ("Flo R", "flo.r@example.org"), ("Zed", "zed@x.io")]
    ):
        world.store.rows[f"u{i}"] = PlatformUser(f"u{i}", email, name, UserStatus.ACTIVE, None)

    assert await world.service.search(q="F", among={"u0", "u1"}) == []
    assert await world.service.search(q="fl", among=set()) == []
    found = await world.service.search(q="Flo", among={"u0", "u1", "u2"})
    assert [u.id for u in found] == ["u1", "u0"]
    assert [u.id for u in await world.service.search(q="flo", among={"u0"})] == ["u0"]
    assert len(await world.service.search(q="o", among={"u0", "u1"})) == 0
    assert len(await world.service.search(q="fl", among={"u0", "u1"}, limit=1)) == 1


@pytest.mark.asyncio
async def test_resend_is_for_invited_people_and_activate_makes_them_active(world):
    made = (await _create(world)).user
    world.mailer.invitations.clear()

    assert await world.service.resend(user_id=made.id, by=ADMIN) is True
    assert world.mailer.invitations[0][2] == Placement("Acme", None, "Research", "member")

    await world.service.activate(made.id)
    assert (await world.service.get(made.id)).status == UserStatus.ACTIVE
    with pytest.raises(AlreadyActiveError):
        await world.service.resend(user_id=made.id, by=ADMIN)
    with pytest.raises(UnknownUserError):
        await world.service.resend(user_id="ghost", by=ADMIN)


@pytest.mark.asyncio
async def test_provision_makes_a_configured_persons_account_as_nexus_and_nothing_else(world):
    world.store.rows["user-seed"] = PlatformUser(
        "user-seed", "sam@example.com", "Sam", UserStatus.INVITED, "builtin"
    )

    made = await world.service.provision("user-seed")

    assert made is not None and made.created
    assert world.idp.calls == [("sam@example.com", None)]
    assert world.store.provisioned == {("builtin", "sub-sam")}
    assert world.store.rows["user-seed"].id == "user-seed" and world.mailer.invitations == []
    again = await world.service.provision("user-seed")
    assert again is not None and not again.created


@pytest.mark.asyncio
async def test_provision_asks_nothing_of_a_provider_that_manages_its_people(world):
    world.store.rows["user-seed"] = PlatformUser(
        "user-seed", "dan@corp.example", "Dan", UserStatus.INVITED, "corp"
    )

    assert await world.service.provision("user-seed") is None
    assert world.store.provisioned == set()
    with pytest.raises(UnknownUserError):
        await world.service.provision("ghost")


@pytest.mark.asyncio
async def test_add_existing_says_when_the_notice_could_not_be_sent(world):
    async def down(**_kwargs):
        raise RuntimeError("smtp down")

    world.mailer.added = down
    _active(world, "carl")
    user = await world.service.add_existing(user_id="carl", grant=WS, by=ADMIN)
    assert world.access.seats["carl"] == {Seat(WS_SCOPE, MEMBERSHIP)}
    assert user.sign_in_email_sent is False


@pytest.mark.asyncio
async def test_adding_someone_invited_sends_their_invitation_again_and_says_so(world):
    world.store.rows["dan"] = PlatformUser(
        "dan", "dan@example.com", "Dan", UserStatus.INVITED, "builtin"
    )
    user = await world.service.add_existing(user_id="dan", grant=WS, by=ADMIN)
    assert user.sign_in_email_sent is True
    assert [i[0] for i in world.mailer.invitations] == ["dan@example.com"]
    assert world.mailer.notices == []


@pytest.mark.asyncio
async def test_creating_and_linking_both_name_the_provider_they_sign_in_with(world):
    created = await _create(world)
    assert created.provider == BUILTIN
    _active(world, "carl")
    linked = await _create(world, email="carl@example.com")
    assert linked.provider == BUILTIN
    world.store.rows["erin"] = PlatformUser(
        "erin", "erin@example.com", "Erin", UserStatus.ACTIVE, "gone"
    )
    gone = await _create(world, email="erin@example.com")
    assert gone.provider is None and Seat(WS_SCOPE, MEMBERSHIP) in world.access.seats["erin"]


@pytest.mark.asyncio
async def test_a_creation_with_no_grant_writes_no_organization_profile(world):
    await _create(world, grant=None, organization_id="org-1", profile={"job_title": "Spy"})
    assert world.store.profiles == {}


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_whether_the_email_has_an_account_or_not(world):
    _active(world, "carl")
    for email in ("carl@example.com", "new@example.com"):
        with pytest.raises(NoProviderError):
            await _create(world, email=email, provider="nope")
    assert world.access.seats.get("carl") is None

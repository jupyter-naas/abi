"""The people service with fakes: the order of a creation (authorized before the
provider is asked), the take-back of a creation that fails after it, linking an
email that has an account, ``provisioning: none``, search, resend, activation."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    AccessGateway,
    AlreadyActiveError,
    AlreadyMemberError,
    EmailTakenError,
    Grant,
    GrantNotHeldError,
    IdentityGateway,
    InvalidPolicyError,
    NewUser,
    NoProviderError,
    OwnerGrantRefusedError,
    PeopleMailer,
    PeopleStorePort,
    Placement,
    PlatformUser,
    ProviderInfo,
    Provisioned,
    ProvisioningFailedError,
    ProvisioningRefused,
    UnknownUserError,
    UserStatus,
    Warrant,
)
from naas_abi.apps.nexus.apps.api.app.services.people.service import UNBOUND_PREFIX, PeopleService

NOW = datetime(2026, 11, 19, 12, 0)
BUILTIN = ProviderInfo("builtin", "Built-in", "https://idp", "builtin")
CORP = ProviderInfo("corp", "Corp SSO", "https://corp", "none")
WS_SCOPE = workspace_container("org-1", "ws-1")
ORG_SCOPE = org_container("org-1")
ADMIN = SimpleNamespace(id="admin", name="Ada")
WS = Grant("workspace", "ws-1", "member")
ORG = Grant("organization", "org-1", "admin")


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
            {"ws-1": "Research"}.get(workspace_id or ""),
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
    """IAM: ``holds`` is what ``admin`` may give, as ``(policy, scope)``."""

    def __init__(self) -> None:
        self.holds = {("builtin.member", WS_SCOPE), ("builtin.admin", ORG_SCOPE)}
        self.pending: dict[str, tuple[str, str, str, str]] = {}
        self.roles: dict[str, dict[str, str]] = {}
        self.policies: set[tuple[str, str, str]] = set()
        self.principals: dict[tuple[str, str], str] = {}
        self.discarded: list[str] = []
        self.fail_role: Exception | None = None
        self.log: list[str] | None = None

    async def scope(self, grant):
        if grant.scope_id == "nope":
            raise LookupError(grant.scope_id)
        if grant.scope == "organization":
            return org_container(grant.scope_id)
        return workspace_container("org-1", grant.scope_id)

    async def warrant(self, provider, email, grants: Sequence[tuple[str, str]], *, by):
        if self.log is not None:
            self.log.append("warrant")
        for policy, scope in grants:
            if (policy, scope) not in self.holds:
                raise GrantNotHeldError(f"{by} does not hold {policy} at {scope}")
        ids = []
        for policy, scope in grants:
            grant_id = f"pgr-{len(self.pending)}"
            self.pending[grant_id] = (provider, email, policy, scope)
            ids.append(grant_id)
        return Warrant(tuple(ids), tuple(ids))

    async def withdraw(self, grant_ids):
        for grant_id in grant_ids:
            self.pending.pop(grant_id, None)

    async def ensure_principal(self, issuer, subject, *, provider, email, name):
        return self.principals.setdefault((issuer, subject), f"usr_{subject}")

    async def discard_principal(self, principal_id):
        self.discarded.append(principal_id)

    async def roles_of(self, user_id):
        return dict(self.roles.get(user_id, {}))

    async def grant_role(self, user_id, role, scope, *, by):
        if self.fail_role is not None:
            raise self.fail_role
        if (f"builtin.{role}", scope) not in self.holds:
            raise GrantNotHeldError(f"{by} does not hold {role} at {scope}")
        self.roles.setdefault(user_id, {})[scope] = role

    async def revoke_role(self, user_id, scope):
        self.roles.get(user_id, {}).pop(scope, None)

    async def attach(self, user_id, policy_id, scope, *, by):
        if (policy_id, scope) not in self.holds:
            raise GrantNotHeldError(f"{by} does not hold {policy_id}")
        made = (user_id, policy_id, scope) not in self.policies
        self.policies.add((user_id, policy_id, scope))
        return made

    async def detach(self, user_id, policy_id, scope):
        self.policies.discard((user_id, policy_id, scope))


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


async def _create(world, email="bob@example.com", grants=(WS,), **kwargs):
    return await world.service.create_or_link(
        email=email,
        name=kwargs.pop("name", "Bob"),
        provider=kwargs.pop("provider", None),
        grants=grants,
        by=ADMIN,
        **kwargs,
    )


# -- creating ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_new_email_is_a_bound_invited_user_with_its_roles_before_any_sign_in(world):
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
    assert world.access.roles[user.id] == {WS_SCOPE: "member"}
    # The warrant has done its part: no pending grant is left to claim.
    assert world.access.pending == {}
    assert world.store.provisioned == {("builtin", "sub-bob")}
    assert world.store.profiles == {("org-1", user.id): {"job_title": "Analyst"}}
    assert result.created and result.provisioned and result.sign_in_email_sent
    assert world.mailer.invitations == [
        ("bob@example.com", "builtin", Placement("Acme", None, "Research", "member"), True)
    ]


@pytest.mark.asyncio
async def test_authorization_runs_before_the_provider_is_asked(world):
    log: list[str] = []
    world.access.log = world.idp.log = log
    await _create(world)
    assert log[:2] == ["warrant", "provision"]

    world.idp.calls.clear()
    with pytest.raises(GrantNotHeldError):
        await _create(world, email="eve@example.com", grants=(Grant("workspace", "ws-1", "admin"),))
    assert world.idp.calls == []  # nobody was made at the provider
    assert await world.service.by_email("eve@example.com") is None


@pytest.mark.asyncio
async def test_only_an_owner_names_an_owner_and_policies_are_customer_ones(world):
    owner = Grant("workspace", "ws-1", "owner")
    with pytest.raises(OwnerGrantRefusedError):
        await _create(world, grants=(owner,))
    with pytest.raises(InvalidPolicyError):
        await _create(world, grants=(Grant("workspace", "ws-1", "member", ("builtin.admin",)),))
    with pytest.raises(ValueError):
        await _create(world, grants=(Grant("workspace", "nope", "member"),))
    assert world.idp.calls == [] and world.store.rows == {}


@pytest.mark.asyncio
async def test_a_failure_after_provisioning_takes_everything_back(world):
    world.access.holds.add(("pol_x", WS_SCOPE))
    world.access.fail_role = RuntimeError("IAM went away")
    with pytest.raises(RuntimeError):
        await _create(world, grants=(Grant("workspace", "ws-1", "member", ("pol_x",)),))

    assert world.idp.deleted == ["sub-bob"]  # the account this call made
    assert world.access.discarded == ["usr_sub-bob"]
    assert world.store.rows == {} and world.store.provisioned == set()
    assert world.access.policies == set()  # the policy attached first is taken back
    assert world.access.pending == {}
    assert world.mailer.invitations == []


@pytest.mark.asyncio
async def test_an_account_the_provider_had_already_is_never_deleted_on_a_failure(world):
    world.idp.accounts["bob@example.com"] = "sub-old"
    world.access.fail_role = RuntimeError("IAM went away")
    with pytest.raises(RuntimeError):
        await _create(world)
    assert world.idp.deleted == [] and world.access.discarded == []
    assert world.store.rows == {}


@pytest.mark.asyncio
async def test_a_provider_failure_makes_nothing_and_withdraws_the_warrant(world):
    world.idp.fails = ProvisioningFailedError("the provider is down")
    with pytest.raises(ProvisioningFailedError):
        await _create(world)
    assert world.store.rows == {} and world.access.pending == {} and world.access.roles == {}


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

    result = await _create(world, email="Carl@example.com")

    assert result.user.id == "carl" and not result.created and not result.provisioned
    assert list(world.store.rows) == ["carl"] and world.idp.calls == []
    assert world.access.roles["carl"] == {WS_SCOPE: "member"}
    # Someone active hears where they were added.
    assert world.mailer.notices == [
        ("carl@example.com", Placement(None, None, "Research", "member"))
    ]
    assert world.mailer.invitations == []


@pytest.mark.asyncio
async def test_linking_an_invited_person_sends_the_invitation_again(world):
    first = await _create(world)
    world.mailer.invitations.clear()

    again = await _create(world, grants=(ORG,))

    assert again.user.id == first.user.id and not again.created
    assert world.access.roles[first.user.id] == {WS_SCOPE: "member", ORG_SCOPE: "admin"}
    assert [m[0] for m in world.mailer.invitations] == ["bob@example.com"]


@pytest.mark.asyncio
async def test_a_role_already_held_where_a_grant_goes_is_already_member(world):
    world.store.rows["carl"] = PlatformUser(
        "carl", "carl@example.com", "Carl", UserStatus.ACTIVE, "x"
    )
    world.access.roles["carl"] = {WS_SCOPE: "viewer"}
    with pytest.raises(AlreadyMemberError):
        await _create(world, email="carl@example.com")
    assert world.access.roles["carl"] == {WS_SCOPE: "viewer"}


@pytest.mark.asyncio
async def test_a_row_made_meanwhile_is_linked(world):
    world.store.taken_on_add = "raced"
    result = await _create(world)
    assert result.user.id == "raced" and not result.created
    assert world.access.roles["raced"] == {WS_SCOPE: "member"}
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
    assert world.access.roles["usr_sub-bob"] == {WS_SCOPE: "member"}
    assert world.access.pending == {} and world.idp.deleted == []
    # A workspace grant alone never rewrites an existing person's organization profile.
    assert world.store.profiles == {}


@pytest.mark.asyncio
async def test_a_workspace_admin_linking_someone_leaves_their_org_profile_alone(world):
    """A workspace admin types the email of an organization member who is not in the
    workspace yet: they are linked and added, and their profile in the organization
    (job title, bio...) stays theirs: editing it is an organization admin's."""
    world.store.rows["alice"] = PlatformUser(
        "alice", "alice@example.com", "Alice", UserStatus.ACTIVE, "builtin"
    )
    world.store.profiles[("org-1", "alice")] = {"job_title": "CFO"}

    result = await _create(
        world, email="alice@example.com", organization_id="org-1", profile={"job_title": "Intern"}
    )

    assert result.user.id == "alice" and not result.created
    assert world.access.roles["alice"] == {WS_SCOPE: "member"}
    assert world.store.profiles == {("org-1", "alice"): {"job_title": "CFO"}}


@pytest.mark.asyncio
async def test_an_org_grant_on_a_link_writes_the_profile(world):
    """Who may give an organization role may edit its people: with an organization
    grant IAM accepted, the link writes the profile."""
    world.store.rows["alice"] = PlatformUser(
        "alice", "alice@example.com", "Alice", UserStatus.ACTIVE, "builtin"
    )

    await _create(
        world,
        email="alice@example.com",
        grants=(ORG,),
        organization_id="org-1",
        profile={"job_title": "CFO"},
    )

    assert world.store.profiles == {("org-1", "alice"): {"job_title": "CFO"}}


@pytest.mark.asyncio
async def test_linking_with_no_grant_writes_no_profile(world):
    world.store.rows["carl"] = PlatformUser(
        "carl", "carl@example.com", "Carl", UserStatus.ACTIVE, "x"
    )
    await _create(
        world,
        email="carl@example.com",
        grants=(),
        organization_id="org-1",
        profile={"job_title": "Spy"},
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
    assert world.access.roles[user.id] == {WS_SCOPE: "member"}
    assert world.access.log == ["warrant"] and world.access.pending == {}
    assert not result.provisioned
    assert world.mailer.invitations[0][1] == "corp"


@pytest.mark.asyncio
async def test_a_platform_invitation_is_made_on_the_inviters_own_right(world):
    result = await _create(world, grants=())
    assert world.idp.calls == [("bob@example.com", "admin")]
    assert result.user.id == "usr_sub-bob" and not result.provisioning_skipped

    world.idp.refuses_user = True
    skipped = await _create(world, email="fay@example.com", grants=())
    assert skipped.provisioning_skipped and skipped.user.id.startswith(UNBOUND_PREFIX)
    assert world.mailer.invitations[-1][3] is False  # the mail promises no code


# -- adding, reading, resending, activating ------------------------------------------------


@pytest.mark.asyncio
async def test_add_existing_attaches_and_tells_them(world):
    world.store.rows["carl"] = PlatformUser(
        "carl", "carl@example.com", "Carl", UserStatus.ACTIVE, "x"
    )
    user = await world.service.add_existing(user_id="carl", grants=(WS,), by=ADMIN)
    assert user.id == "carl" and world.access.roles["carl"] == {WS_SCOPE: "member"}
    assert len(world.mailer.notices) == 1
    # Still the person (a ``PlatformUser``), and whether the notice went.
    assert isinstance(user, PlatformUser) and user.sign_in_email_sent is True

    with pytest.raises(AlreadyMemberError):
        await world.service.add_existing(user_id="carl", grants=(WS,), by=ADMIN)
    with pytest.raises(UnknownUserError):
        await world.service.add_existing(user_id="ghost", grants=(WS,), by=ADMIN)
    with pytest.raises(GrantNotHeldError):
        await world.service.add_existing(
            user_id="carl", grants=(Grant("organization", "org-1", "member"),), by=ADMIN
        )


@pytest.mark.asyncio
async def test_search_needs_two_characters_and_stays_among_the_ids_given(world):
    for i, (name, email) in enumerate(
        [("Florent", "florent@naas.ai"), ("Flo R", "florent.frv@gmail.com"), ("Zed", "zed@x.io")]
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
    """The configuration's people (core/org_seed.py): their row is unbound and names
    its provider; the account is made as Nexus (no inviting person), recorded as
    ABI's, and the row stays as it is (their verified sign-in binds it), unmailed."""
    world.store.rows["user-seed"] = PlatformUser(
        "user-seed", "sam@example.com", "Sam", UserStatus.INVITED, "builtin"
    )

    made = await world.service.provision("user-seed")

    assert made is not None and made.created
    assert world.idp.calls == [("sam@example.com", None)]
    assert world.store.provisioned == {("builtin", "sub-sam")}
    assert world.store.rows["user-seed"].id == "user-seed" and world.mailer.invitations == []
    # Again: found at the provider, nothing new recorded.
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
    world.store.rows["carl"] = PlatformUser(
        "carl", "carl@example.com", "Carl", UserStatus.ACTIVE, "x"
    )
    user = await world.service.add_existing(user_id="carl", grants=(WS,), by=ADMIN)
    # The membership stands; the answer says nobody was told.
    assert world.access.roles["carl"] == {WS_SCOPE: "member"}
    assert user.sign_in_email_sent is False


@pytest.mark.asyncio
async def test_adding_someone_invited_sends_their_invitation_again_and_says_so(world):
    world.store.rows["dan"] = PlatformUser(
        "dan", "dan@example.com", "Dan", UserStatus.INVITED, "builtin"
    )
    user = await world.service.add_existing(user_id="dan", grants=(WS,), by=ADMIN)
    assert user.sign_in_email_sent is True
    assert [i[0] for i in world.mailer.invitations] == ["dan@example.com"]
    assert world.mailer.notices == []


@pytest.mark.asyncio
async def test_creating_and_linking_both_name_the_provider_they_sign_in_with(world):
    created = await _create(world)
    assert created.provider == BUILTIN
    world.store.rows["carl"] = PlatformUser(
        "carl", "carl@example.com", "Carl", UserStatus.ACTIVE, "builtin"
    )
    linked = await _create(world, email="carl@example.com")
    assert linked.provider == BUILTIN
    # A provider no longer configured is not named, and the link stands.
    world.store.rows["erin"] = PlatformUser(
        "erin", "erin@example.com", "Erin", UserStatus.ACTIVE, "gone"
    )
    gone = await _create(world, email="erin@example.com")
    assert gone.provider is None and world.access.roles["erin"] == {WS_SCOPE: "member"}


@pytest.mark.asyncio
async def test_a_creation_with_no_grant_writes_no_organization_profile(world):
    """An organization's profile is written only with a grant it gave (a platform
    invitation names none)."""
    await _create(world, grants=(), organization_id="org-1", profile={"job_title": "Spy"})
    assert world.store.profiles == {}


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused_whether_the_email_has_an_account_or_not(world):
    """The answer does not tell an address with an account from a new one."""
    world.store.rows["carl"] = PlatformUser(
        "carl", "carl@example.com", "Carl", UserStatus.ACTIVE, "builtin"
    )
    for email in ("carl@example.com", "new@example.com"):
        with pytest.raises(NoProviderError):
            await _create(world, email=email, provider="nope")
    assert world.access.roles.get("carl") is None

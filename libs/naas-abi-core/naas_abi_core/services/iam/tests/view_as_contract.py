"""Viewing as a principal: who may view as whom, and where.

The cast is the permission scenario's (``examples/permission_scenario/journeys.py``):
Root, Acme (Olivia), Alpha and Bravo (its workspaces), Bob, Carol, Dave and
"Alpha minimal", plus Beta Corp for another organisation. The scenarios run in
process (``IAMService_view_as_test.py``); a decision on a view is in process only,
like ``link_user``.

``as_user(record)`` is a context manager yielding the ``IAMService`` a call makes
as that user.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    use_call_context,
)
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import (
    PrincipalRecord,
    ViewAsRefused,
    ViewAsVerdict,
)
from naas_abi_core.services.iam.IAMService import IAMService, view_as_resource
from naas_abi_core.services.iam.tests.grant_contract import NEXUS, features
from naas_abi_core.services.iam.tests.iam_harness import (
    below,
    document,
    org,
    statement,
    workspace,
)

ISSUER = "https://idp.example"
ACME, BETA = "acme", "beta"
ACME_SCOPE, BETA_SCOPE = org(ACME), org(BETA)
ACME_WIDE = below(ACME)
ALPHA, BRAVO = workspace("alpha", ACME), workspace("bravo", ACME)
BETA_WS = workspace("beta-ws", BETA)

AsUser = Callable[[PrincipalRecord], AbstractContextManager[IAMService]]


@dataclass
class Cast:
    root: PrincipalRecord  # the platform admin
    root2: PrincipalRecord  # another platform admin
    olivia: PrincipalRecord  # Acme's admin, below it, holding "Acme access" there
    bob: PrincipalRecord  # Alpha's owner
    carol: PrincipalRecord  # Alpha's admin, holding "Alpha access"
    carla: PrincipalRecord  # Alpha's admin with "Alpha access" and a Deny of chat
    dave: PrincipalRecord  # Alpha's viewer, in group "Alpha minimal"
    eve: PrincipalRecord  # Alpha's member
    frank: PrincipalRecord  # Alpha's viewer
    zed: PrincipalRecord  # Alpha's member, given "Acme access" at Alpha
    sam: PrincipalRecord  # Alpha's member, suspended
    nobody: PrincipalRecord  # Bravo's member: nothing at Alpha
    paul: PrincipalRecord  # Beta Corp's member
    service: PrincipalRecord
    minimal: PrincipalRecord  # the group "Alpha minimal"
    ok: PrincipalRecord  # a group owned by Alpha, holding "Alpha minimal"
    owners: PrincipalRecord  # a group owned by Alpha, holding builtin.owner
    acme_access: str
    alpha_access: str
    alpha_minimal: str


def cast(iam: IAMService) -> Cast:
    with as_service_account("engine"):
        iam.register_catalog(NEXUS)
    with as_service_account("api"):
        for org_id in (ACME, BETA):
            iam.register_container("nexus", "organization", org_id)
        for ws, parent in (("alpha", ACME_SCOPE), ("bravo", ACME_SCOPE)):
            iam.register_container("nexus", "workspace", ws, parent=parent)
        iam.register_container("nexus", "workspace", "beta-ws", parent=BETA_SCOPE)
    with as_service_account("engine"):
        names = [
            "root",
            "root2",
            "olivia",
            "bob",
            "carol",
            "carla",
            "dave",
            "eve",
            "frank",
            "zed",
            "sam",
            "nobody",
            "paul",
        ]
        u = {name: iam.ensure_user(ISSUER, name) for name in names}
        service = iam.create_service_account("ci/nightly")
        acme_access = iam.create_policy(
            "Acme access", features("chat", "search", "maps"), scope=ACME_SCOPE
        )
        alpha_access = iam.create_policy(
            "Alpha access",
            features("chat", "search"),
            scope=ALPHA,
            parent=acme_access.id,
        )
        alpha_minimal = iam.create_policy(
            "Alpha minimal", features("chat"), scope=ALPHA, parent=alpha_access.id
        )
        no_chat = iam.create_policy(
            "No chat",
            document(
                statement("Deny", ["nexus:UseFeature"], ["${scope}/nexus:feature/chat"])
            ),
        )
        attach = iam.attach_policy
        attach(roles.PLATFORM_ADMIN, u["root"].id)
        attach(roles.PLATFORM_ADMIN, u["root2"].id)
        attach(roles.ADMIN, u["olivia"].id, ACME_SCOPE)
        attach(roles.ADMIN, u["olivia"].id, ACME_WIDE)
        attach(acme_access.id, u["olivia"].id, ACME_WIDE)
        attach(roles.OWNER, u["bob"].id, ALPHA)
        for name in ("carol", "carla"):
            attach(roles.ADMIN, u[name].id, ALPHA)
            attach(alpha_access.id, u[name].id, ALPHA)
        attach(no_chat.id, u["carla"].id, ALPHA)
        for name in ("dave", "frank"):
            attach(roles.VIEWER, u[name].id, ALPHA)
        for name in ("eve", "zed", "sam"):
            attach(roles.MEMBER, u[name].id, ALPHA)
        attach(acme_access.id, u["zed"].id, ALPHA)
        attach(roles.MEMBER, u["nobody"].id, BRAVO)
        attach(roles.MEMBER, u["paul"].id, BETA_WS)
        iam.suspend_principal(u["sam"].id)
        minimal = iam.create_group("Alpha minimal", scope=ALPHA)
        attach(alpha_minimal.id, minimal.id, ALPHA)
        iam.add_group_member(minimal.id, u["dave"].id)
        ok = iam.create_group("analysts", scope=ALPHA)
        attach(alpha_minimal.id, ok.id, ALPHA)
        owners = iam.create_group("owners", scope=ALPHA)
        attach(roles.OWNER, owners.id, ALPHA)
    return Cast(
        service=service,
        minimal=minimal,
        ok=ok,
        owners=owners,
        acme_access=acme_access.id,
        alpha_access=alpha_access.id,
        alpha_minimal=alpha_minimal.id,
        **u,
    )


def verdict(
    as_user: AsUser,
    caller: PrincipalRecord,
    person: PrincipalRecord,
    container: str = ALPHA,
    groups: tuple[str, ...] = (),
) -> ViewAsVerdict:
    with as_user(caller) as iam:
        return iam.view_as_verdict(person.id, container, groups)


def allowed(
    as_user: AsUser,
    caller: PrincipalRecord,
    person: PrincipalRecord,
    container: str = ALPHA,
    groups: tuple[str, ...] = (),
) -> None:
    found = verdict(as_user, caller, person, container, groups)
    assert found.allowed, found.reason
    assert found.reason is None and found.code is None
    with as_user(caller) as iam:
        iam.require_view_as(person.id, container, groups)  # does not raise


def refused(
    as_user: AsUser,
    caller: PrincipalRecord,
    person: PrincipalRecord,
    code: str,
    *named: str,
    container: str = ALPHA,
    groups: tuple[str, ...] = (),
) -> str:
    """The view is refused for ``code``, the message naming ``named``; the same
    refusal ``require_view_as`` raises."""
    found = verdict(as_user, caller, person, container, groups)
    assert not found.allowed
    assert found.code == code, (found.code, found.reason)
    reason = found.reason or ""
    for part in named:
        assert part in reason, reason
    with as_user(caller) as iam, pytest.raises(ViewAsRefused) as raised:
        iam.require_view_as(person.id, container, groups)
    assert str(raised.value) == reason
    assert raised.value.code == code
    return reason


# -- allowed ----------------------------------------------------------------------------


def run_platform_admin_views_as_a_workspace_admin(iam, as_user) -> None:
    c = cast(iam)
    allowed(as_user, c.root, c.carol)
    allowed(as_user, c.root, c.bob)  # an owner too: nobody but a platform admin is out
    allowed(as_user, c.root, c.nobody, BRAVO)
    allowed(as_user, c.root, c.paul, BETA_WS)


def run_org_admin_views_as_a_member_of_its_workspaces(iam, as_user) -> None:
    c = cast(iam)
    allowed(as_user, c.olivia, c.eve)
    allowed(as_user, c.olivia, c.nobody, BRAVO)
    # What a person holds below Acme's access is within what Olivia holds.
    allowed(as_user, c.olivia, c.dave)
    allowed(as_user, c.olivia, c.zed)
    allowed(as_user, c.olivia, c.carol)


def run_workspace_admin_views_as_a_member_with_a_sub_policy_they_hold(
    iam, as_user
) -> None:
    c = cast(iam)
    # Dave: viewer, and "Alpha minimal" through a group, a sub-policy of Carol's
    # "Alpha access": it grants nothing beyond what she holds.
    allowed(as_user, c.carol, c.dave)
    allowed(as_user, c.carol, c.eve)
    allowed(as_user, c.carol, c.frank)
    allowed(as_user, c.bob, c.eve)


def run_api_acting_for_the_viewer_decides_as_the_viewer(iam, as_user) -> None:
    """Nexus calls as ``api``, on behalf of the viewer: the viewer's own rights
    decide, never ``api``'s."""
    c = cast(iam)

    def as_api(viewer: PrincipalRecord):
        return use_call_context(
            CallContext(
                principal=Principal(id="api", kind="service_account", name="api"),
                on_behalf_of=Principal(id=viewer.id, kind="user"),
            )
        )

    with as_api(c.carol):
        assert iam.view_as_verdict(c.dave.id, ALPHA).allowed
        found = iam.view_as_verdict(c.bob.id, ALPHA)
        assert not found.allowed and found.code == "holds_more"
    with as_api(c.eve):
        found = iam.view_as_verdict(c.frank.id, ALPHA)
        assert not found.allowed and found.code == "not_allowed"


# -- refused ----------------------------------------------------------------------------


def run_org_admin_for_a_member_of_another_organisation(iam, as_user) -> None:
    c = cast(iam)
    # In Beta Corp's workspace Olivia holds nothing: no right to view there.
    refused(as_user, c.olivia, c.paul, "not_allowed", container=BETA_WS)
    # In her own, Paul holds nothing.
    refused(as_user, c.olivia, c.paul, "nothing_held", container=ALPHA)


def run_workspace_admin_for_the_org_admin(iam, as_user) -> None:
    c = cast(iam)
    reason = refused(
        as_user, c.carol, c.olivia, "holds_more", roles.ADMIN, f"below {ACME_SCOPE}"
    )
    # Olivia's attachment at the organisation's own level is not counted at Alpha.
    assert f"attached at {ACME_SCOPE}" not in reason, reason


def run_workspace_admin_for_the_workspace_owner(iam, as_user) -> None:
    c = cast(iam)
    refused(as_user, c.carol, c.bob, "holds_more", roles.OWNER, ALPHA)
    refused(as_user, c.carol, c.bob, "holds_more", "builtin.owner")


def run_workspace_admin_for_someone_given_the_org_access_policy(iam, as_user) -> None:
    c = cast(iam)
    # "Acme access" at Alpha: Carol holds "Alpha access", a sub-policy of it:
    # not its maps.
    refused(as_user, c.carol, c.zed, "holds_more", c.acme_access, "Acme access", ALPHA)
    # The owner holds no feature, so none of "Alpha access" either.
    refused(as_user, c.bob, c.carol, "holds_more", c.alpha_access)


def run_nobody_views_as_the_platform_admin(iam, as_user) -> None:
    c = cast(iam)
    for caller in (c.olivia, c.carol, c.bob):
        found = verdict(as_user, caller, c.root, ALPHA)
        assert not found.allowed and found.code in ("platform_admin", "not_allowed")
    # Olivia and Bob may view in Alpha: it is Root they may not view as.
    refused(as_user, c.olivia, c.root, "platform_admin", roles.PLATFORM_ADMIN)
    refused(as_user, c.root, c.root2, "platform_admin", roles.PLATFORM_ADMIN)
    refused(as_user, c.root2, c.root, "platform_admin")
    refused(as_user, c.root, c.root, "self")


def run_oneself_a_group_a_service_account(iam, as_user) -> None:
    c = cast(iam)
    refused(as_user, c.carol, c.carol, "self")
    refused(as_user, c.root, c.root, "self")
    refused(as_user, c.root, c.minimal, "not_a_user", "group")
    refused(as_user, c.root, c.service, "not_a_user", "service account")
    refused(as_user, c.carol, c.minimal, "not_a_user")


def run_a_suspended_or_deleted_person(iam, as_user) -> None:
    c = cast(iam)
    refused(as_user, c.root, c.sam, "inactive", "suspended")
    refused(as_user, c.carol, c.sam, "inactive")
    with as_service_account("engine"):
        iam.delete_principal(c.frank.id)
    refused(as_user, c.root, c.frank, "inactive", "deleted")


def run_someone_who_holds_nothing_there(iam, as_user) -> None:
    c = cast(iam)
    refused(as_user, c.root, c.nobody, "nothing_held", ALPHA)
    refused(as_user, c.carol, c.nobody, "nothing_held")
    refused(as_user, c.root, c.paul, "nothing_held", container=BRAVO)
    # What IAM keeps for the roles, and the person's own page, is nothing.
    with as_service_account("engine"):
        solo = iam.ensure_user(ISSUER, "solo")
    refused(as_user, c.root, solo, "nothing_held")


def run_a_member_or_a_viewer_for_anyone(iam, as_user) -> None:
    c = cast(iam)
    for caller in (c.eve, c.frank, c.dave, c.zed):
        for person in (c.eve, c.frank, c.carol, c.bob, c.root):
            if person.id == caller.id:
                continue
            refused(as_user, caller, person, "not_allowed", "iam:ViewAs")
    # Nor in a container where they hold nothing.
    refused(as_user, c.eve, c.nobody, "not_allowed", container=BRAVO)


def run_a_deny_of_the_caller_that_overlaps(iam, as_user) -> None:
    c = cast(iam)
    allowed(as_user, c.carol, c.dave)
    # Carla's Deny of chat overlaps the chat Dave's "Alpha minimal" grants.
    reason = refused(as_user, c.carla, c.dave, "holds_more", "Deny", c.alpha_minimal)
    assert "Alpha minimal" in reason
    # No Deny on Eve's grants: the same caller views him.
    allowed(as_user, c.carla, c.eve)


def run_the_message_names_the_first_policy_not_held(iam, as_user) -> None:
    c = cast(iam)
    reason = refused(as_user, c.carol, c.olivia, "holds_more")
    # The policy, and where it is attached: below the organisation.
    assert roles.ADMIN in reason, reason
    assert f"attached below {ACME_SCOPE}" in reason, reason


# -- groups -----------------------------------------------------------------------------


def run_identity_provider_groups_add_their_attachments(iam, as_user) -> None:
    c = cast(iam)
    allowed(as_user, c.carol, c.eve)
    # A group Carol's access covers: still allowed.
    allowed(as_user, c.carol, c.eve, groups=(c.ok.id,))
    # A group that holds the owner role at Alpha: refused, naming the policy, where
    # it is attached and the group.
    reason = refused(
        as_user,
        c.carol,
        c.eve,
        "holds_more",
        roles.OWNER,
        ALPHA,
        "owners",
        groups=(c.owners.id,),
    )
    assert c.owners.id in reason, reason
    # The stored groups count with them: Dave's "Alpha minimal" and the group.
    refused(as_user, c.carol, c.dave, "holds_more", roles.OWNER, groups=(c.owners.id,))
    allowed(as_user, c.carol, c.dave, groups=(c.ok.id,))
    # The platform admin holds the owner role through `*`.
    allowed(as_user, c.root, c.eve, groups=(c.owners.id,))
    # Not an id of a group: it lends nothing, and cannot make the view refused.
    allowed(as_user, c.carol, c.eve, groups=(c.bob.id, "grp_unknown"))
    # An empty person: the groups alone do not make it a view of someone who holds
    # nothing at the container.
    refused(as_user, c.carol, c.nobody, "nothing_held", groups=())
    # A group at another container does not count here.
    with as_service_account("engine"):
        elsewhere = iam.create_group("bravo owners", scope=BRAVO)
        iam.attach_policy(roles.OWNER, elsewhere.id, BRAVO)
    allowed(as_user, c.carol, c.eve, groups=(elsewhere.id,))
    # Below the organisation, the group reaches Alpha.
    with as_service_account("engine"):
        wide = iam.create_group("acme owners", scope=ACME_SCOPE)
        iam.attach_policy(roles.OWNER, wide.id, ACME_WIDE)
    refused(
        as_user,
        c.carol,
        c.eve,
        "holds_more",
        roles.OWNER,
        "below",
        "acme owners",
        groups=(wide.id,),
    )
    # A person who holds only what the groups give still holds something there.
    allowed(as_user, c.carol, c.nobody, groups=(c.ok.id,))


def run_an_unproven_grant_is_refused(iam, as_user) -> None:
    """The budget rules of "Grant only what you hold": past the budget a grant is
    not proven and the view is refused."""
    from naas_abi_core.services.iam import grants

    c = cast(iam)
    allowed(as_user, c.carol, c.dave)
    saved = grants.CALL_BUDGET
    grants.CALL_BUDGET = 0
    grants._covered.cache_clear()  # a proof made before costs nothing now
    try:
        found = verdict(as_user, c.carol, c.zed)
        assert not found.allowed
        assert found.code == "holds_more", found.reason
        assert "too long" in (found.reason or ""), found.reason
    finally:
        grants.CALL_BUDGET = saved
        grants._covered.cache_clear()


# -- what the roles give ------------------------------------------------------------------


def run_the_roles_give_view_as_at_a_workspace_and_below_an_organisation(
    iam, as_user
) -> None:
    c = cast(iam)

    def may(who: PrincipalRecord, container: str, person: str = "usr_x") -> bool:
        with as_user(who) as session:
            return session.authorize(
                "iam:ViewAs", view_as_resource(person, container)
            ).allowed

    # An admin or an owner at a workspace: that workspace.
    for who in (c.carol, c.bob):
        assert may(who, ALPHA)
        assert not may(who, BRAVO)
        assert not may(who, ACME_SCOPE)
        assert not may(who, BETA_WS)
        assert not may(who, "abi:")
    # Below the organisation: the organisation's own level and every workspace.
    assert may(c.olivia, ALPHA) and may(c.olivia, BRAVO)
    assert may(c.olivia, ACME_SCOPE)
    assert not may(c.olivia, BETA_WS) and not may(c.olivia, BETA_SCOPE)
    assert not may(c.olivia, "abi:")
    # Members and viewers hold none of it.
    for who in (c.eve, c.zed, c.dave, c.frank):
        assert not may(who, ALPHA)
    # The platform admin, through `*`, everywhere.
    for container in (ALPHA, BRAVO, ACME_SCOPE, BETA_WS, "abi:"):
        assert may(c.root, container)
    # A member of a workspace has none at another, nor an unscoped holder.
    assert not may(c.nobody, ALPHA) and not may(c.paul, ALPHA)
    # Attached at the organisation alone, an admin views at its own level only.
    with as_service_account("engine"):
        solo = iam.ensure_user(ISSUER, "org-level")
        iam.attach_policy(roles.ADMIN, solo.id, BETA_SCOPE)
    assert may(solo, BETA_SCOPE) and not may(solo, BETA_WS)


SCENARIOS = [
    run_platform_admin_views_as_a_workspace_admin,
    run_org_admin_views_as_a_member_of_its_workspaces,
    run_workspace_admin_views_as_a_member_with_a_sub_policy_they_hold,
    run_api_acting_for_the_viewer_decides_as_the_viewer,
    run_org_admin_for_a_member_of_another_organisation,
    run_workspace_admin_for_the_org_admin,
    run_workspace_admin_for_the_workspace_owner,
    run_workspace_admin_for_someone_given_the_org_access_policy,
    run_nobody_views_as_the_platform_admin,
    run_oneself_a_group_a_service_account,
    run_a_suspended_or_deleted_person,
    run_someone_who_holds_nothing_there,
    run_a_member_or_a_viewer_for_anyone,
    run_a_deny_of_the_caller_that_overlaps,
    run_the_message_names_the_first_policy_not_held,
    run_identity_provider_groups_add_their_attachments,
    run_an_unproven_grant_is_refused,
    run_the_roles_give_view_as_at_a_workspace_and_below_an_organisation,
]

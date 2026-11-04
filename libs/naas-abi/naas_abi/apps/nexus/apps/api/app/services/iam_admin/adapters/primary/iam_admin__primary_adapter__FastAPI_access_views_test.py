"""A person's, a group's and a policy's access at every level, as each viewer may list
it: ``/attachments?principal_id=`` and ``?policy_id=`` across levels,
``/principals/{id}/groups`` (IAM's ``list_principal_groups``) and the platform's search
for a person (``/principals?q=``). IAM decides every row; Nexus adds no check."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.primary.iam_admin__primary_adapter__FastAPI_test import (  # noqa: E501, F401 - pytest fixtures
    audit,
    get,
    world,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER

ORG1 = org_container("org-1")
WS2 = workspace_container("org-1", "ws-2")
ONTOLOGY_DEMO = workspace_container("org-9", "ws-9")

READER = {
    "version": "2026-10-13",
    "statements": [
        {
            "effect": "Allow",
            "actions": ["triple_store:Query"],
            "resources": ["${scope}/triple_store:graph/*"],
        }
    ],
}


@pytest.fixture
def bob(world):  # noqa: F811 - imported pytest fixtures
    """Bob, as QA found him: a member of organisation org-1, of its workspace ws-2 and of
    "Ontology demo" (ws-9, another organisation); "Bob: BFO only" at Ontology demo; "W
    analysts" at ws-2 through group G. ``ws2admin`` administers ws-2 only."""
    nexus = world.nexus
    iam = nexus.iam
    nexus.workspace("org-1", "ws-2")
    nexus.workspace("org-9", "ws-9")
    # The roles first: the profile is the one his sign-in brings.
    nexus.grant("bob", "member", ORG1)
    nexus.grant("bob", "member", WS2)
    nexus.grant("bob", "member", ONTOLOGY_DEMO)
    with as_service_account("api"):
        record = iam.ensure_user(
            LEGACY_NEXUS_ISSUER,
            "bob",
            provider="nexus",
            email="bob-9a4bcd@example.com",
            display_name="Bob",
        )
    nexus.grant("ws2admin", "admin", WS2)
    with as_service_account("engine"):
        bfo = iam.create_policy("Bob: BFO only", READER, scope=ONTOLOGY_DEMO)
        iam.attach_policy(bfo.id, record.id, ONTOLOGY_DEMO)
        analysts = iam.create_policy("W analysts", READER, scope=WS2)
        group = iam.create_group("G", scope=WS2)
        iam.attach_policy(analysts.id, group.id, WS2)
        iam.add_group_member(group.id, record.id)
        demo_group = iam.create_group("Demo team", scope=ONTOLOGY_DEMO)
        iam.add_group_member(demo_group.id, record.id)
    return SimpleNamespace(
        id=record.id, bfo=bfo.id, analysts=analysts.id, group=group.id, demo_group=demo_group.id
    )


def held(world, bob, user: str) -> set[tuple[str, str | None]]:  # noqa: F811
    answer = get(world, f"/attachments?principal_id={bob.id}", user)
    assert answer.status_code == 200, (user, answer.text)
    return {(a["policy_id"], a["scope"]) for a in answer.json()["items"]}


def groups(world, bob, user: str) -> set[str]:  # noqa: F811
    answer = get(world, f"/principals/{bob.id}/groups", user)
    assert answer.status_code == 200, (user, answer.text)
    return {g["id"] for g in answer.json()["items"]}


def test_the_platform_admin_sees_everything_bob_holds(world, bob):  # noqa: F811
    seen = held(world, bob, "root")
    assert {
        ("builtin.member", ORG1),
        ("builtin.member", WS2),
        ("builtin.member", ONTOLOGY_DEMO),
        (bob.bfo, ONTOLOGY_DEMO),
    } <= seen
    assert groups(world, bob, "root") == {bob.group, bob.demo_group}
    # Each row names its policy and where the policy is owned, for the link to its owner.
    rows = get(world, f"/attachments?principal_id={bob.id}").json()["items"]
    bfo = next(a for a in rows if a["policy_id"] == bob.bfo)
    assert bfo["policy_name"] == "Bob: BFO only"
    assert bfo["policy_owner_scope"] == ONTOLOGY_DEMO
    assert bfo["principal"]["email"] == "bob-9a4bcd@example.com"
    member = next(a for a in rows if a["policy_id"] == "builtin.member")
    assert member["policy_owner_scope"] == "abi:"
    # What reaches him through G: the group's attachments, at every level.
    through = get(world, f"/attachments?principal_id={bob.group}").json()["items"]
    assert [(a["policy_id"], a["scope"]) for a in through] == [(bob.analysts, WS2)]


def test_an_organisations_admin_sees_what_is_inside_it(world, bob):  # noqa: F811
    seen = held(world, bob, "admin")
    assert ("builtin.member", ORG1) in seen and ("builtin.member", WS2) in seen
    assert all(scope and scope.startswith(ORG1) for _, scope in seen), seen
    assert (bob.bfo, ONTOLOGY_DEMO) not in seen
    assert groups(world, bob, "admin") == {bob.group}


def test_a_workspaces_admin_sees_what_iam_lets_them_list(world, bob):  # noqa: F811
    seen = held(world, bob, "ws2admin")
    assert ("builtin.member", WS2) in seen
    assert all(scope == WS2 for _, scope in seen), seen
    assert groups(world, bob, "ws2admin") == {bob.group}
    # The group's page: its attachment at ws-2.
    through = get(world, f"/attachments?principal_id={bob.group}", "ws2admin").json()["items"]
    assert [(a["policy_id"], a["scope"]) for a in through] == [(bob.analysts, WS2)]


def test_a_member_sees_nothing(world, bob):  # noqa: F811
    # Across levels, IAM keeps each attachment the caller may list: none for a member.
    assert held(world, bob, "member") == set()
    assert groups(world, bob, "member") == set()
    rows = get(world, f"/attachments?policy_id={bob.analysts}", "member")
    assert rows.status_code == 200 and rows.json()["items"] == []
    assert get(world, "/principals?kind=user&q=bob", "member").status_code == 403
    # The lists of a level, and the whole list, stay refused to whoever may list none.
    assert get(world, f"/attachments?scope={WS2}", "member").status_code == 403
    assert get(world, "/attachments", "member").status_code == 403


def test_nothing_held_across_levels_is_an_empty_list_not_a_refusal(world, bob):  # noqa: F811
    """A workspace's or an organisation's admin holds no right on the platform's
    attachments: a policy of theirs attached nowhere, or a person holding nothing
    they may list, is an empty list."""
    with as_service_account("engine"):
        unattached = world.nexus.iam.create_policy("W readers", READER, scope=WS2)
        loner = world.nexus.iam.ensure_user(LEGACY_NEXUS_ISSUER, "loner", provider="nexus")
    for user in ("ws2admin", "admin"):
        answer = get(world, f"/attachments?policy_id={unattached.id}", user)
        assert answer.status_code == 200 and answer.json()["items"] == [], (user, answer.text)
        answer = get(world, f"/attachments?principal_id={loner.id}", user)
        assert answer.status_code == 200 and answer.json()["items"] == [], (user, answer.text)


def test_a_policys_page_lists_where_it_is_attached_and_to_whom(world, bob):  # noqa: F811
    for user in ("root", "admin", "ws2admin"):
        rows = get(world, f"/attachments?policy_id={bob.analysts}", user).json()["items"]
        assert [(a["principal_id"], a["principal"]["kind"], a["scope"]) for a in rows] == [
            (bob.group, "group", WS2)
        ], user
    # Another organisation's policy is not listed to org-1's admin: none of its rows.
    assert get(world, f"/attachments?policy_id={bob.bfo}", "admin").json()["items"] == []


def test_the_platform_finds_a_person_by_a_search_text(world, bob):  # noqa: F811
    for text in ("bob-9a4", "BOB-9A4BCD@EXAMPLE.COM", bob.id):
        found = get(world, f"/principals?kind=user&q={text}").json()["items"]
        assert [p["id"] for p in found] == [bob.id], text
    assert get(world, "/principals?kind=user&q=nobody-at-all").json()["items"] == []
    # Whoever may list no principal finds no one: refused, as the list is.
    assert get(world, "/principals?kind=user&q=bob", "admin").status_code == 403

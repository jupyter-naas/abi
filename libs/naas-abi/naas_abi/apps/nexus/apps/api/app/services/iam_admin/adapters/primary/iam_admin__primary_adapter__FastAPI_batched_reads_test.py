"""Batched Settings reads (#1608): the Groups list with each group's member count in one
request (no detail per group), a person's and their groups' attachments in one request,
each authorized exactly as the per-item reads it replaces, with explicit bounds."""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.primary.iam_admin__primary_adapter__FastAPI_test import (  # noqa: E501, F401 - pytest fixtures
    as_,
    audit,
    get,
    world,
    ws2,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import (
    GROUPS_PAGE_MAX,
    MAX_PRINCIPALS_PER_READ,
    IamAdminService,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER

ORG1 = org_container("org-1")
WS1 = workspace_container("org-1", "ws-1")
WS2 = workspace_container("org-1", "ws-2")
OTHER_WS = workspace_container("org-9", "ws-9")

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
def holder(world):  # noqa: F811 - pytest fixtures
    """Dana: a member of org-1, of its ws-2 and of another organisation's ws-9, a policy of
    her own at ws-9, a group at ws-2 holding a policy there and a group at ws-9.
    ``ws2admin`` administers ws-2 only."""
    nexus = world.nexus
    iam = nexus.iam
    nexus.workspace("org-1", "ws-2")
    nexus.workspace("org-9", "ws-9")
    for scope in (ORG1, WS2, OTHER_WS):
        nexus.grant("dana", "member", scope)
    nexus.grant("ws2admin", "admin", WS2)
    with as_service_account("api"):
        record = iam.ensure_user(LEGACY_NEXUS_ISSUER, "dana", provider="nexus")
    with as_service_account("engine"):
        own = iam.create_policy("Dana: reader", READER, scope=OTHER_WS)
        iam.attach_policy(own.id, record.id, OTHER_WS)
        analysts = iam.create_policy("W analysts", READER, scope=WS2)
        group = iam.create_group("G", scope=WS2)
        iam.attach_policy(analysts.id, group.id, WS2)
        iam.add_group_member(group.id, record.id)
        other = iam.create_group("Other team", scope=OTHER_WS)
        iam.add_group_member(other.id, record.id)
    return SimpleNamespace(id=record.id, group=group.id, other_group=other.id)


class CountingGateway(EngineIamGateway):
    """The engine's gateway, counting the per-principal name lookups a read makes."""

    def __init__(self) -> None:
        self.principal_reads = 0

    def principal(self, principal_id: str):  # type: ignore[no-untyped-def]
        self.principal_reads += 1
        return super().principal(principal_id)


@pytest.fixture
def counted(world, audit) -> Iterator[CountingGateway]:  # noqa: F811 - pytest fixtures
    gateway = CountingGateway()
    previous = runtime.configure(lambda: IamAdminService(gateway, audit))
    yield gateway
    runtime.configure(previous)


def _people(world, count: int, prefix: str = "p", *, at: str | None = None) -> list[str]:  # noqa: F811
    """``count`` people, members of ``at`` when given (a container's group takes only
    people related to it)."""
    if at is not None:
        for i in range(count):
            world.nexus.grant(f"{prefix}{i}", "member", at)
    with as_service_account("engine"):
        return [
            world.nexus.iam.ensure_user(LEGACY_NEXUS_ISSUER, f"{prefix}{i}").id
            for i in range(count)
        ]


def _groups(world, count: int, people: list[str], scope: str | None = None) -> list[str]:  # noqa: F811
    """``count`` groups owned by ``scope``; group ``i`` has ``i % 7`` of ``people``."""
    ids = []
    with as_service_account("engine"):
        for i in range(count):
            group = world.nexus.iam.create_group(f"g{i:03d}", scope=scope)
            for member in people[: i % 7]:
                world.nexus.iam.add_group_member(group.id, member)
            ids.append(group.id)
    return ids


def _expected_count(world, group_id: str, user: str, **headers: str) -> int | None:  # noqa: F811
    """The count the old page derived: the detail's members, or none when it is refused."""
    detail = world.client.get(f"/api/iam/admin/groups/{group_id}", headers={**as_(user), **headers})
    return len(detail.json()["members"]) if detail.status_code == 200 else None


# -- the Groups list: counts in the list, one request ----------------------------------------


def test_the_groups_list_carries_each_member_count_in_one_request(world, counted):  # noqa: F811
    people = _people(world, 6)
    ids = _groups(world, 50, people)

    answer = get(world, "/groups?member_counts=true")
    assert answer.status_code == 200, answer.text
    items = {g["id"]: g for g in answer.json()["items"]}
    assert set(ids) <= set(items)
    for i, group_id in enumerate(ids):
        assert items[group_id]["member_count"] == i % 7
        # A summary, never the members themselves.
        assert "members" not in items[group_id]
    # No member was named to count them.
    assert counted.principal_reads == 0

    # What the page read before: one detail per group, naming each member.
    details = [get(world, f"/groups/{group_id}") for group_id in ids]
    assert counted.principal_reads == sum(i % 7 for i in range(50))
    listed = len(answer.content)
    one_by_one = len(get(world, "/groups").content) + sum(len(d.content) for d in details)
    assert listed < one_by_one / 2, (listed, one_by_one)


def test_without_the_flag_the_list_is_as_before(world):  # noqa: F811
    _groups(world, 3, _people(world, 3))
    items = get(world, "/groups").json()["items"]
    assert items and all("member_count" not in g for g in items)


@pytest.mark.parametrize(
    "user,scope",
    [
        ("root", None),
        ("root", ORG1),
        ("admin", ORG1),
        ("admin", WS2),
        ("ws2admin", WS2),
    ],
)
def test_a_count_is_shown_exactly_where_the_group_could_be_read(world, ws2, user, scope):  # noqa: F811
    """At a workspace the organization's groups are listed to whoever attaches there; their
    count is shown only to whoever may read the group, as its detail was."""
    colleagues = _people(world, 2, "c", at=WS2)
    org_group = _groups(world, 3, colleagues, scope=ORG1)
    ws_group = _groups(world, 3, colleagues, scope=WS2)
    path = "/groups?member_counts=true" + (f"&scope={scope}" if scope else "")
    answer = get(world, path, user)
    assert answer.status_code == 200, answer.text
    items = answer.json()["items"]
    assert {g["id"] for g in items} & set(org_group + ws_group)
    for item in items:
        assert item["member_count"] == _expected_count(world, item["id"], user), item["name"]
    counts = {g["id"]: g["member_count"] for g in items}
    if user == "ws2admin":
        # The organization's groups are listed to attach to, never read: no count.
        assert {counts.get(g) for g in org_group} == {None}
        assert [counts[g] for g in ws_group] == [0, 1, 2]


def test_a_count_is_refused_where_the_list_is(world, ws2):  # noqa: F811
    _groups(world, 2, [], scope=WS1)
    assert get(world, f"/groups?member_counts=true&scope={WS1}", "ws2admin").status_code == 403
    assert get(world, "/groups?member_counts=true", "stranger").status_code == 403
    assert get(world, "/groups?member_counts=true", "member").status_code == 403


def test_in_a_view_a_group_outside_it_has_no_count(world):  # noqa: F811
    """As its detail is refused there (``view_as/AGENTS.md``, "Confined to the workspace")."""
    people = _people(world, 2, at=WS1)
    mine = _groups(world, 1, people, scope=WS1)
    with as_service_account("engine"):
        world.nexus.iam.add_group_member(mine[0], people[0])
        theirs = world.nexus.iam.create_group("org team", scope=ORG1)
        world.nexus.iam.add_group_member(theirs.id, people[1])
    view = {"x-view-container": WS1}
    answer = world.client.get(
        f"/api/iam/admin/groups?member_counts=true&scope={WS1}", headers={**as_("root"), **view}
    )
    assert answer.status_code == 200, answer.text
    counts = {g["id"]: g["member_count"] for g in answer.json()["items"]}
    assert counts[mine[0]] == 1 == _expected_count(world, mine[0], "root", **view)
    assert counts[theirs.id] is None
    assert _expected_count(world, theirs.id, "root", **view) is None


def test_the_list_is_paged_in_a_stable_order_up_to_an_explicit_bound(world):  # noqa: F811
    """500 groups: pages of an explicit size, every group once, in IAM's order."""
    ids = set(_groups(world, 500, _people(world, 6)))
    seen: list[str] = []
    after: str | None = None
    requests = 0
    while True:
        path = "/groups?member_counts=true&limit=200"
        answer = get(world, path + (f"&after={after}" if after else ""))
        requests += 1
        assert answer.status_code == 200, answer.text
        body = answer.json()
        assert len(body["items"]) <= 200
        seen += [g["id"] for g in body["items"]]
        after = body["next_after"]
        if after is None:
            break
    assert requests == -(-len(seen) // 200) == 3
    assert ids <= set(seen) and len(seen) == len(set(seen))
    whole = get(world, f"/groups?member_counts=true&limit={GROUPS_PAGE_MAX}").json()
    assert [g["id"] for g in whole["items"]] == seen[:GROUPS_PAGE_MAX]
    assert whole["next_after"] is None and len(seen) == GROUPS_PAGE_MAX
    # The default page is IAM's, 100; a page larger than the bound is refused.
    assert len(get(world, "/groups").json()["items"]) == 100
    assert get(world, f"/groups?limit={GROUPS_PAGE_MAX + 1}").status_code == 422
    assert get(world, "/groups?limit=0").status_code == 422


# -- a person's page: their and their groups' attachments in one request -------------------


def _rows(answer) -> list[tuple[str, str, str | None]]:  # type: ignore[no-untyped-def]
    assert answer.status_code == 200, answer.text
    return [(a["principal_id"], a["policy_id"], a["scope"]) for a in answer.json()["items"]]


@pytest.mark.parametrize("user", ["root", "admin", "ws2admin", "member"])
def test_several_principals_attachments_are_read_at_once_as_one_by_one(world, holder, user):  # noqa: F811
    principals = [holder.id, holder.group, holder.other_group]
    one_by_one = [
        row for p in principals for row in _rows(get(world, f"/attachments?principal_id={p}", user))
    ]
    query = "&".join(f"principal_id={p}" for p in principals)
    assert _rows(get(world, f"/attachments?{query}", user)) == one_by_one
    # A principal named twice is read once.
    twice = f"/attachments?principal_id={holder.id}&principal_id={holder.id}"
    assert _rows(get(world, twice, user)) == _rows(
        get(world, f"/attachments?principal_id={holder.id}", user)
    )


def test_at_a_scope_the_batch_keeps_the_level_rule(world, holder):  # noqa: F811
    query = f"principal_id={holder.id}&principal_id={holder.group}&scope={WS2}"
    rows = _rows(get(world, f"/attachments?{query}", "ws2admin"))
    assert rows and all(scope == WS2 for _, _, scope in rows)
    # Whoever may list nothing at the level is refused, as for one principal.
    assert get(world, f"/attachments?{query}", "member").status_code == 403


def test_a_batch_is_bounded(world):  # noqa: F811
    many = "&".join(f"principal_id=usr_{i}" for i in range(MAX_PRINCIPALS_PER_READ + 1))
    refused = get(world, f"/attachments?{many}")
    assert refused.status_code == 422
    allowed = "&".join(f"principal_id=usr_{i}" for i in range(MAX_PRINCIPALS_PER_READ))
    assert get(world, f"/attachments?{allowed}").status_code == 200


def test_a_person_in_many_groups_is_read_in_one_request(world, counted):  # noqa: F811
    """A person in 60 groups, each holding a policy: one request reads every row, and
    each policy and principal is named once."""
    person = _people(world, 1, "many")[0]
    groups = _groups(world, 60, [], scope=None)
    with as_service_account("engine"):
        policy = world.nexus.iam.create_policy(
            "readers",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["triple_store:Query"],
                        "resources": ["abi:triple_store:graph/*"],
                    }
                ],
            },
        )
        for group_id in groups:
            world.nexus.iam.add_group_member(group_id, person)
            world.nexus.iam.attach_policy(policy.id, group_id)
    query = "&".join(f"principal_id={p}" for p in [person, *groups])
    answer = get(world, f"/attachments?{query}")
    rows = _rows(answer)
    assert {p for p, _, _ in rows} == set(groups)
    assert counted.principal_reads == len(groups)  # each group named once, the person holds none
    assert len(json.dumps(answer.json())) < 60 * 1024

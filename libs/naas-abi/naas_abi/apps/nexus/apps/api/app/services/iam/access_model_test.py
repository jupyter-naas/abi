"""The access move (``access_model``) on the stores of the previous versions.

Two worlds: ``policy_tree_test``'s (the sets moved to policies, the names to
container paths, S2's records made for every container: roles still attached to
each person) and ``role_features_test``'s taken back to before #1585 ("<X>
members" groups in the records, "Features of <role>" beside each role, a
deny-list ceiling). On each, a decision matrix over people × actions × containers
is asked before and after the move, independently of the move's own probes, and
diffed: every change is in the report, in its direction, with a reason, and the
narrowings are the intended ones."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.models import UserModel
from naas_abi.apps.nexus.apps.api.app.services.iam import (
    access_model,
    container_defaults,
    container_names,
    platform_files,
    policy_tree,
    role_features,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import policy_tree_test as previous
from naas_abi.apps.nexus.apps.api.app.services.iam import role_features_test as features_world
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    SqlDefaultsStore,
    members_name,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.levels import LEVELS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree_test import (  # noqa: F401
    _remote_agents,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    SECTIONS,
    TYPE_OF_KIND,
    in_offer_form,
    offer_document,
    offer_of,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam.policy import MAX_PATTERNS, POLICY_VERSION, parse_policy_document
from sqlalchemy import inspect, text

KIND = {TYPE_OF_KIND[k]: k for k in SECTIONS}
UNIVERSE = access_model.Universe(
    **{
        kind: frozenset((m, n) for t, m, n in previous.ITEMS if KIND.get(t) == kind)
        for kind in SECTIONS
    },
    declared=frozenset({"acme_people"}),
)
ROLE_POLICIES = set(access_model.ROLE_POLICIES)
# The narrowings the ADR intends, and those of the model it names (a module's
# declared actions leave the offer; shared graphs: write is the admins'; a Viewer
# uses the Viewer features).
NARROWINGS = {
    "members_lose_workflows",
    "owners_lose_delete",
    "org_member_role",
    "model_sets",
    "module_actions",
    "shared_graphs",
    "viewer_features",
}


def _settings(admin: str | None = None, models: tuple[str, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(
        migration=SimpleNamespace(default_workspace_admin=admin),
        models=SimpleNamespace(member_set=list(models)),
    )


async def _move(nexus_db, nexus, **kwargs):
    """The move as a start makes it, then its decisions compared as the start
    leaves them to (``complete_report``): the whole report."""
    nexus.iam.invalidate()
    async with nexus_db() as db:
        report = await access_model.migrate_access(
            db,
            universe=kwargs.pop("universe", UNIVERSE),
            settings=kwargs.pop("settings", _settings()),
            iam=nexus.iam,
            **kwargs,
        )
    nexus.iam.invalidate()
    if report is not None and report.decisions == access_model.PENDING:
        report = await access_model.complete_report(nexus_db, iam=nexus.iam)
        nexus.iam.invalidate()
    return report


async def _recorded(nexus_db, name: str) -> str | None:
    async with nexus_db() as db:
        row = (
            await db.execute(text("SELECT report FROM iam_migrations WHERE name = :n"), {"n": name})
        ).first()
    return None if row is None else str(row[0])


def _changes(report: access_model.Report, *, what: bool = False) -> set[tuple]:
    return {
        (c.user_id, c.container, c.kind, c.reason, *((tuple(c.what),) if what else ()))
        for c in report.changes
    }


def _snapshot(nexus) -> tuple:
    """What IAM holds: policies (and revisions), attachments, groups and members."""
    with as_service_account("engine"):
        iam = nexus.iam
        policies = {(p.id, p.revision) for p in iam._all_policies()}
        attachments = {(a.policy_id, a.principal_id, a.scope) for a in iam.list_attachments()}
        groups = {
            (g.id, g.name, g.status, g.membership_of, frozenset(iam.list_group_members(g.id)))
            for g in access_model._pages(iam.list_groups)
        }
    return policies, attachments, groups


async def _defaults(nexus_db) -> set:
    async with nexus_db() as db:
        return set(await SqlDefaultsStore(db).all())


# -- the worlds ---------------------------------------------------------------------------


async def _policy_tree_world_installed(nexus, nexus_db):
    """``policy_tree_test``'s world at this version's start, before the access move:
    the sets' move, the names', and S2's records (``container_defaults_v1``)."""
    await previous._upgrade(nexus, nexus_db)
    async with nexus_db() as db:
        await container_defaults.migrate(db)
    nexus.iam.invalidate()
    return nexus


def _containers(world) -> dict[str, str]:
    return {ws: workspace_container(org, ws) for ws, org in world.WORKSPACES.items()}


def _matrix(nexus, subjects, world=previous) -> dict[tuple, bool]:
    """Each subject's decisions: every module item, declared action and feature of
    every workspace (``policy_tree_test._names``), its custom agents, and the
    workspaces' and organizations' deletes and settings."""
    names: dict[tuple, tuple[str, str]] = {}
    if world is previous:
        names.update(previous._names(previous._new))
    else:
        for (ws, key), resource in {
            (ws, key): features_world._feature(nexus, org, ws, key)
            for ws, org in world.WORKSPACES.items()
            for key in world.KNOWN_FEATURE_KEYS
        }.items():
            names[(ws, "feature", key)] = ("nexus:UseFeature", resource)
    for ws, container in _containers(world).items():
        names[(ws, "delete", "workspace")] = ("nexus:DeleteWorkspace", container)
        names[(ws, "update", "workspace")] = ("nexus:UpdateWorkspace", container)
        names[(ws, "read", "workspace")] = ("nexus:GetWorkspace", container)
    for org in sorted({o for o in world.WORKSPACES.values() if o}):
        names[(org, "delete", "organization")] = ("nexus:DeleteOrganization", org_container(org))
        names[(org, "read", "organization")] = ("nexus:GetOrganization", org_container(org))
    found: dict[tuple, bool] = {}
    for subject in subjects:
        label = "sa" if subject.startswith("sa:") else subject  # one id per world
        with use_call_context(previous._context(subject, nexus)):
            for key, (action, resource) in names.items():
                found[(label, *key)] = nexus.iam.authorize(action, resource).allowed
    found["names"] = names  # type: ignore[index]
    return found


def _diff(before: dict, after: dict) -> dict[tuple, bool]:
    return {k: v for k, v in after.items() if k != "names" and before[k] != v}


def _asked(action: str, resource: str) -> str:
    """A decision as the report names it; a module's declared action by its
    resource type (the move asks it on a resource of its own)."""
    if action.partition(":")[0] not in ("nexus", "module", "model_registry", "triple_store"):
        resource = resource.rsplit("/", 1)[0]
    return f"{action} on {resource}"


def _check_report(report: access_model.Report, changed: dict[tuple, bool], names: dict) -> None:
    """Every change of a person is in the report, in its direction; no reason is
    "unexplained"; every narrowing is one the ADR names."""
    reported: dict[tuple[str, str], set[str]] = {}
    for change in report.changes:
        reported.setdefault((change.user_id, change.kind), set()).update(
            _asked(*w.split(" on ", 1)) for w in change.what
        )
    missing = []
    for (subject, *key), allowed in changed.items():
        action, resource = names[tuple(key)]
        kind = "widening" if allowed else "narrowing"
        if _asked(action, resource) not in reported.get((subject, kind), set()):
            missing.append((subject, kind, action, resource))
    assert missing == []
    assert report.unexplained() == []
    assert {c.reason for c in report.narrowings()} <= NARROWINGS
    assert report.unverified == []


# -- the decisions -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_change_of_access_is_reported_with_its_reason(nexus_db):
    nexus = previous._world()
    with nexus.installed():
        subjects = previous._subjects(nexus)
        await previous._upgrade(nexus, nexus_db)
        async with nexus_db() as db:
            await container_defaults.migrate(db)
        nexus.iam.invalidate()
        before = _matrix(nexus, subjects)
        report = await _move(nexus_db, nexus)
        assert report is not None and report.applied
        after = _matrix(nexus, subjects)
        changed = _diff(before, after)
        _check_report(report, changed, before["names"])
        # Nobody is a person who is not one: the service account's and the
        # platform admin's decisions are as they were.
        assert not [k for k in changed if k[0] in ("sa", "root")]
        # The intended ones, labelled.
        reasons = {(c.user_id, c.reason) for c in report.changes}
        assert ("alice", "owners_lose_delete") in reasons
        assert ("henry", "owners_lose_delete") in reasons
        assert ("jack", "members_lose_workflows") in reasons
        assert all(c.intended for c in report.changes if c.reason == "model_sets")
        assert changed[("alice", "ws-a", "delete", "workspace")] is False
        # Nothing per person is left of the roles; the groups say who is where.
        with as_service_account("engine"):
            held = [
                a
                for a in nexus.iam.list_attachments()
                if a.policy_id in ROLE_POLICIES and a.principal_id.startswith("usr")
            ]
            assert held == []
            levels = LEVELS.get(nexus.iam)
            members = set(nexus.iam.list_group_members(levels.members))
            viewers = set(nexus.iam.list_group_members(levels.viewers))
        assert nexus.principal("carol") in members and nexus.principal("frank") in viewers
        # Each ceiling is an offer now.
        records = {r.container: r for r in await _defaults(nexus_db)}
        with as_service_account("engine"):
            for container in _containers(previous).values():
                document = nexus.iam.get_policy(records[container].access_policy_id).document
                assert in_offer_form(document), container
        # Kept, and said: the policies attached to one person.
        assert any("Full access" in k for k in report.kept_attachments)
        assert not any("Platform member" in k for k in report.kept_attachments)
        assert sorted(report.no_admin) == sorted(
            [_containers(previous)["ws-b"], _containers(previous)["ws-c"]]
        )
        assert report.drive_flags == []
        kept = json.loads(await _recorded(nexus_db, access_model.MIGRATION_NAME) or "{}")
        assert kept["applied"] and kept["people"] == report.people
        assert await _recorded(nexus_db, access_model.PLANNED_NAME) is None


@pytest.mark.asyncio
async def test_the_start_moves_and_the_decisions_are_compared_afterwards(nexus_db, tmp_path):
    from naas_abi.apps.nexus.apps.api.app.core.database import Base
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    # The same world, moved and reported in one go, on a database of its own.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'other.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    other_db = async_sessionmaker(engine, expire_on_commit=False)
    clean = previous._world()
    with clean.installed():
        subjects = previous._subjects(clean)
        await _policy_tree_world_installed(clean, other_db)
        whole = await _move(other_db, clean)
        expected = _matrix(clean, subjects)
    await engine.dispose()
    assert whole is not None and whole.decisions == access_model.COMPARED

    nexus = previous._world()
    with nexus.installed():
        await _policy_tree_world_installed(nexus, nexus_db)
        nexus.iam.invalidate()
        # The start: the move is made and recorded; comparing every person's
        # decisions before and after (most of the move's time) is left for later.
        async with nexus_db() as db:
            started = await access_model.migrate_access(
                db, universe=UNIVERSE, settings=_settings(), iam=nexus.iam
            )
        nexus.iam.invalidate()
        assert started is not None and started.applied
        assert started.decisions == access_model.PENDING and started.changes == []
        assert _diff(expected, _matrix(nexus, previous._subjects(nexus))) == {}
        recorded = json.loads(await _recorded(nexus_db, access_model.MIGRATION_NAME) or "{}")
        assert recorded["decisions"] == access_model.PENDING
        assert await _recorded(nexus_db, access_model.PLANNED_NAME)
        # Afterwards: the report of the whole move, from IAM as it was before it.
        report = await access_model.complete_report(nexus_db, iam=nexus.iam)
        assert report is not None and report.decisions == access_model.COMPARED
        assert _changes(report, what=True) == _changes(whole, what=True)
        assert report.unverified == []
        recorded = json.loads(await _recorded(nexus_db, access_model.MIGRATION_NAME) or "{}")
        assert recorded["decisions"] == access_model.COMPARED and recorded["changes"]
        assert await _recorded(nexus_db, access_model.PLANNED_NAME) is None
        # Once compared, nothing is left to compare.
        assert await access_model.complete_report(nexus_db, iam=nexus.iam) is None


@pytest.mark.asyncio
async def test_a_dry_run_reports_what_the_move_does_and_writes_nothing(nexus_db):
    nexus = previous._world()
    with nexus.installed():
        nexus = await _policy_tree_world_installed(nexus, nexus_db)
        held, records = _snapshot(nexus), await _defaults(nexus_db)
        dry = await _move(nexus_db, nexus, dry_run=True)
        assert dry is not None and dry.dry_run and not dry.applied
        assert _snapshot(nexus) == held and await _defaults(nexus_db) == records
        assert await _recorded(nexus_db, access_model.MIGRATION_NAME) is None
        assert await _recorded(nexus_db, access_model.PLANNED_NAME) is None
        applied = await _move(nexus_db, nexus)
    assert applied is not None
    assert _changes(dry, what=True) == _changes(applied, what=True)


async def _holding_table(nexus_db, rows: list[tuple[str, bool, bool]]) -> None:
    async with nexus_db() as db:
        await db.execute(
            text(
                f"CREATE TABLE {platform_files.HOLDING_TABLE} (workspace_id TEXT PRIMARY KEY, "
                "platform_drive_enabled BOOLEAN, system_drive_enabled BOOLEAN)"
            )
        )
        for row in rows:
            await db.execute(
                text(f"INSERT INTO {platform_files.HOLDING_TABLE} VALUES (:w, :p, :s)"),
                {"w": row[0], "p": row[1], "s": row[2]},
            )
        await db.commit()


async def _has_holding_table(nexus_db) -> bool:
    async with nexus_db() as db:
        connection = await db.connection()
        return await connection.run_sync(
            lambda sync: inspect(sync).has_table(platform_files.HOLDING_TABLE)
        )


@pytest.mark.asyncio
async def test_the_drive_flags_are_given_to_the_people_of_the_workspace_after_the_move(nexus_db):
    """``platform_drive_enabled`` (kept by 0073) becomes Platform Files · read and
    write for the workspace's people once they are in its groups; the dry run
    reports it and keeps the table."""
    nexus = previous._world()
    with nexus.installed():
        nexus = await _policy_tree_world_installed(nexus, nexus_db)
        await _holding_table(nexus_db, [("ws-a", True, True)])
        dry = await _move(nexus_db, nexus, dry_run=True)
        assert dry is not None
        assert {(r["workspace_id"], r["flag"], r["action"]) for r in dry.drive_flags} == {
            ("ws-a", "platform", "converted"),
            ("ws-a", "system", "reported"),
        }
        assert await _has_holding_table(nexus_db)
        with as_service_account("engine"):
            assert platform_files.platform_files_groups(nexus.iam) == {}
        report = await _move(nexus_db, nexus)
        assert report is not None
        assert {(r["flag"], r["action"]) for r in report.drive_flags} == {
            ("platform", "converted"),
            ("system", "reported"),
        }
        assert not await _has_holding_table(nexus_db)
        container = _containers(previous)["ws-a"]
        with as_service_account("engine"):
            assert platform_files.workspace_platform_files(nexus.iam, "ws-a") == "write"
            group = platform_files.platform_files_groups(nexus.iam)["ws-a"]
            members = set(nexus.iam.list_group_members(group))
            assert members and members == platform_files.people_of(nexus.iam, container)
        kept = json.loads(await _recorded(nexus_db, access_model.MIGRATION_NAME) or "{}")
        assert len(kept["drive_flags"]) == 2


@pytest.mark.asyncio
async def test_the_cli_dry_run_reports_and_writes_nothing(nexus_db, tmp_path):
    """``abi iam migrate-access --dry-run`` (``migrate_from_cli``): on the database
    the CLI names, with the engine's IAM it opened."""
    nexus = previous._world()
    with nexus.installed():
        await _policy_tree_world_installed(nexus, nexus_db)
        held, records = _snapshot(nexus), await _defaults(nexus_db)
        report = await access_model.migrate_from_cli(
            f"sqlite+aiosqlite:///{tmp_path / 'nexus.sqlite'}",
            SimpleNamespace(iam=nexus.iam),
            settings=_settings(),
            universe=UNIVERSE,
        )
        assert report is not None and report.dry_run and report.changes
        assert any(line.startswith("Access move (dry run)") for line in report.lines())
        assert _snapshot(nexus) == held and await _defaults(nexus_db) == records
        assert await _recorded(nexus_db, access_model.MIGRATION_NAME) is None
        assert await _recorded(nexus_db, access_model.PLANNED_NAME) is None


@pytest.mark.asyncio
async def test_once_and_again_changes_nothing(nexus_db):
    nexus = previous._world()
    with nexus.installed():
        await _policy_tree_world_installed(nexus, nexus_db)
        assert await _move(nexus_db, nexus) is not None
        held, records = _snapshot(nexus), await _defaults(nexus_db)
        # Recorded: a start does not run it again.
        assert await _move(nexus_db, nexus) is None
        # Forced, it finds nothing to do.
        again = await _move(nexus_db, nexus, force=True)
        assert again is not None
        assert again.changes == [] and again.memberships == [] and again.detached == 0
        assert again.retired_policies == [] and again.retired_groups == []
        assert again.converted_records == [] and again.converted_ceilings == []
        assert _snapshot(nexus) == held and await _defaults(nexus_db) == records


@pytest.mark.asyncio
async def test_an_interrupted_move_ends_as_an_uninterrupted_one(nexus_db, tmp_path, monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.core.database import Base
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    # The same world moved in one go, on a database of its own.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'other.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    other_db = async_sessionmaker(engine, expire_on_commit=False)
    clean = previous._world()
    with clean.installed():
        subjects = previous._subjects(clean)
        await _policy_tree_world_installed(clean, other_db)
        whole = await _move(other_db, clean)
        expected = _matrix(clean, subjects)
    await engine.dispose()
    assert whole is not None

    nexus = previous._world()
    with nexus.installed():
        await _policy_tree_world_installed(nexus, nexus_db)
        real = nexus.iam.detach_policy
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 6:
                raise RuntimeError("the store went away")
            return real(*args, **kwargs)

        # Applied to the real IAM only: the copy is another service.
        monkeypatch.setattr(nexus.iam, "detach_policy", flaky)
        assert await _move(nexus_db, nexus) is None
        assert calls["n"] >= 6
        assert await _recorded(nexus_db, access_model.MIGRATION_NAME) is None
        # Kept before the real IAM changed: IAM as it was, which the report is read from.
        planned = await _recorded(nexus_db, access_model.PLANNED_NAME)
        assert planned and json.loads(planned)["before"]["policies"]
        monkeypatch.setattr(nexus.iam, "detach_policy", real)
        finished = await _move(nexus_db, nexus)
        assert finished is not None and finished.applied
        after = _matrix(nexus, previous._subjects(nexus))
    assert _diff(expected, after) == {}
    # The report is the whole move's, from the state before it.
    assert _changes(finished) == _changes(whole)
    assert await _recorded(nexus_db, access_model.PLANNED_NAME) is None


@pytest.mark.asyncio
async def test_a_shape_it_does_not_know_stops_the_move_with_nothing_recorded(nexus_db, caplog):
    nexus = previous._world()
    with nexus.installed():
        await _policy_tree_world_installed(nexus, nexus_db)
        ws_a = _containers(previous)["ws-a"]
        records = {r.container: r for r in await _defaults(nexus_db)}
        with as_service_account("engine"):
            ceiling = nexus.iam.get_policy(records[ws_a].access_policy_id)
            document = ceiling.document.to_dict()
            document["statements"].append(
                {
                    "sid": "Odd",
                    "effect": "Deny",
                    "actions": ["module:UseAgent"],
                    "resources": ["${scope}/module:agent/*"],
                }
            )
            nexus.iam.update_policy(
                ceiling.id, expected_revision=ceiling.revision, document=document
            )
        held, kept = _snapshot(nexus), await _defaults(nexus_db)
        assert await _move(nexus_db, nexus) is None
        assert _snapshot(nexus) == held and await _defaults(nexus_db) == kept
        assert await _recorded(nexus_db, access_model.MIGRATION_NAME) is None
        assert await _recorded(nexus_db, access_model.PLANNED_NAME) is None
        assert "stopped" in caplog.text and "denies every" in caplog.text


def test_a_ceiling_of_more_modules_than_one_statement_holds_becomes_an_offer_in_parts():
    modules = [f"client{i:03}" for i in range(MAX_PATTERNS + 50)]
    universe = access_model.Universe(agents=frozenset((m, "Agent") for m in modules))
    ceiling = {
        "version": POLICY_VERSION,
        "statements": [
            {
                "sid": "Agents",
                "effect": "Allow",
                "actions": ["module:UseAgent"],
                "resources": ["${scope}/module:agent/*"],
            },
            {
                "sid": "OtherWorkspaces",
                "effect": "Deny",
                "actions": ["module:UseAgent"],
                "resources": [f"${{scope}}/module:agent/{modules[0]}/*"],
            },
        ],
    }
    offer, _dropped = access_model.ceiling_offer(ceiling, universe=universe, features=())
    assert len(offer.agents) == len(modules) - 1
    document = offer_document(offer)
    parse_policy_document(document)
    assert [s["sid"] for s in document["statements"]] == ["OfferAgents", "OfferAgents2"]
    assert offer_of(document) == offer


@pytest.mark.asyncio
async def test_it_waits_for_the_records_of_container_defaults(nexus_db, caplog):
    nexus = previous._world()
    with nexus.installed():
        await previous._upgrade(nexus, nexus_db)
        held = _snapshot(nexus)
        assert await _move(nexus_db, nexus) is None
        assert _snapshot(nexus) == held
    assert container_defaults.MIGRATION_NAME in caplog.text


# -- the default admin -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_role_another_one_already_gives_goes_and_is_said(nexus_db):
    """What another role of theirs already gives goes, and the report names it: an
    organization's admin holds no admins group of its workspaces; a platform admin
    holds no organization's or workspace's admins group (as a store moved by a build of
    before this rule left them: the move run again takes them out). The workspace groups
    stay (they bound what their people see), and nobody loses a decision for it."""
    nexus = previous._world()
    scopes = _containers(previous)
    nexus.grant("root", "admin", nexus.org("org-1"))
    nexus.grant("root", "admin", scopes["ws-a"])
    nexus.grant("alice", "admin", scopes["ws-b"])
    with nexus.installed():
        subjects = previous._subjects(nexus)
        await _policy_tree_world_installed(nexus, nexus_db)
        before = _matrix(nexus, subjects)
        report = await _move(nexus_db, nexus)
        assert report is not None and report.applied
        changed = _diff(before, _matrix(nexus, subjects))
        # Everyone's changes are reported but a platform admin's gains: out of the
        # workspaces' roles, no offer bounds them, and the move does not probe Nexus
        # agents one by one. They lose nothing.
        _check_report(report, {k: v for k, v in changed.items() if k[0] != "root"}, before["names"])
        assert not [k for k, allowed in changed.items() if not allowed and k[0] == "root"]
        assert report.redundant == [
            "alice left Workspace ws-b admins: an admin of its organization (org-1): "
            "their role reaches every workspace of it"
        ]
        records = {r.container: r for r in await _defaults(nexus_db)}
        org1 = org_container("org-1")
        with as_service_account("engine"):
            root = str(nexus.iam.resolve_user("root").id)
            alice = str(nexus.iam.resolve_user("alice").id)

        def members(group_id) -> set:
            with as_service_account("engine"):
                return set(nexus.iam.list_group_members(group_id))

        assert alice in members(records[org1].admins_group_id)
        assert alice not in members(records[scopes["ws-b"]].admins_group_id)
        assert alice in members(records[scopes["ws-b"]].members_group_id)
        # A platform admin left in the admins groups (a store moved by a build of before
        # this rule): written in the store, as IAM of today ties no one there.
        nexus.iam.store.add_group_member(records[org1].admins_group_id, root)
        nexus.iam.store.add_group_member(records[scopes["ws-a"]].admins_group_id, root)
        nexus.iam.invalidate()
        held = _matrix(nexus, subjects)
        again = await _move(nexus_db, nexus, force=True)
        assert again is not None
        assert sorted(again.redundant) == [
            "root left ORG-1 admins: " + access_model.PLATFORM_ADMIN_COVERS,
            "root left Workspace ws-a admins: " + access_model.PLATFORM_ADMIN_COVERS,
        ]
        assert root not in members(records[org1].admins_group_id)
        assert root not in members(records[scopes["ws-a"]].admins_group_id)
        # Nothing lost: a platform admin may do everything.
        lost = _diff(held, _matrix(nexus, subjects))
        assert not [k for k, allowed in lost.items() if not allowed]


def test_a_platform_admin_stays_the_admin_of_an_organization_that_has_no_other():
    org_a, org_b = org_container("a"), org_container("b")
    by_group = {"grp_a": (org_a, "admins"), "grp_b": (org_b, "admins")}
    root = access_model.PersonPlan("usr_root", "root", platform_admin=True)
    ann = access_model.PersonPlan("usr_ann", "ann")
    plans = {"usr_root": root, "usr_ann": ann}
    groups = {"usr_root": {"grp_a", "grp_b"}, "usr_ann": {"grp_a"}}
    access_model._drop_redundant(plans, by_group, groups)
    # Ann administers "a": root leaves it; nobody else does "b": root stays.
    assert root.leaves == ["grp_a"] and [g for g, _ in root.redundant] == ["grp_a"]
    assert ann.leaves == [] and ann.redundant == []


@pytest.mark.asyncio
async def test_the_default_admin_is_made_admin_of_each_workspace_with_none(nexus_db):
    nexus = previous._world()
    with nexus.installed():
        await _policy_tree_world_installed(nexus, nexus_db)
        async with nexus_db() as db:
            db.add(UserModel(id="ivan", email="ivan@example.com", name="Ivan"))
            await db.commit()
        report = await _move(nexus_db, nexus, settings=_settings("Ivan@Example.com"))
        assert report is not None
        ws_b, ws_c = _containers(previous)["ws-b"], _containers(previous)["ws-c"]
        assert report.no_admin == []
        assert sorted(report.default_admin_added) == sorted([ws_b, ws_c])
        assert report.default_admin == "ivan@example.com"
        records = {r.container: r for r in await _defaults(nexus_db)}
        ivan = nexus.principal("ivan")
        with as_service_account("engine"):
            for container in (ws_b, ws_c):
                assert ivan in nexus.iam.list_group_members(records[container].admins_group_id)
                assert ivan in nexus.iam.list_group_members(records[container].members_group_id)
        with use_call_context(NexusIam.context("ivan")):
            assert nexus.iam.authorize("nexus:UpdateWorkspace", ws_c).allowed
        assert {c.reason for c in report.changes if c.user_id == "ivan"} <= {
            "default_admin",
            "model_sets",
        }


@pytest.mark.asyncio
async def test_a_default_admin_nexus_does_not_know_lists_the_workspaces(nexus_db):
    nexus = previous._world()
    with nexus.installed():
        await _policy_tree_world_installed(nexus, nexus_db)
        report = await _move(nexus_db, nexus, settings=_settings("nobody@example.com"))
    assert report is not None and report.default_admin_added == []
    assert len(report.no_admin) == 2


# -- a store from before #1585 ---------------------------------------------------------------


def _deny_list(document: dict) -> dict:
    return {
        "version": document.get("version", "2012-10-17"),
        "statements": [
            {
                "sid": "Modules",
                "effect": "Allow",
                "actions": ["module:*"],
                "resources": ["${scope}/module:agent/*", "${scope}/module:app/*"],
            },
            {
                "sid": "TurnedOff",
                "effect": "Deny",
                "actions": ["module:UseAgent"],
                "resources": ["${scope}/module:agent/acme.people/B"],
            },
            {
                "sid": "Features",
                "effect": "Allow",
                "actions": ["nexus:UseFeature"],
                "resources": ["${scope}/nexus:feature/*"],
            },
        ],
    }


async def _before_1585(nexus, nexus_db) -> None:
    """S2's records taken back to the previous version's: "<X> members" (no
    membership group) holding each container's people, "<W> access" held by "<W>
    admins" at W, a deny-list ceiling."""
    store_records = await _defaults(nexus_db)
    async with nexus_db() as db:
        orgs, workspaces = await container_defaults.read_nexus(db)
    labels = {org_container(o): n for o, n in orgs.items()}
    labels.update({workspace_container(o, w): n for w, (o, n) in workspaces.items()})
    old: list[container_defaults.DefaultsRecord] = []
    with as_service_account("api"):
        iam = nexus.iam
        holders: dict[str, set[str]] = {}
        for attachment in iam.list_attachments():
            if (
                attachment.policy_id in ROLE_POLICIES
                and attachment.scope
                and container_defaults.is_user(attachment.principal_id)
            ):
                holders.setdefault(attachment.scope, set()).add(attachment.principal_id)
        for record in store_records:
            container, label = record.container, labels[record.container]
            for a in iam.list_attachments(principal_id=record.members_group_id):
                iam.detach_policy(a.policy_id, record.members_group_id, a.scope)
            iam.delete_group(record.members_group_id)
            members = iam.create_group(members_name(label), scope=container)
            for person in sorted(holders.get(container, set())):
                iam.add_group_member(members.id, person)
            if container.endswith(tuple(f"/{w}" for w in workspaces)):
                iam.attach_policy(record.access_policy_id, record.admins_group_id, container)
                policy = iam.get_policy(record.access_policy_id)
                if container == workspace_container("org-1", "ws-a"):
                    iam.update_policy(
                        policy.id,
                        expected_revision=policy.revision,
                        document=_deny_list(policy.document.to_dict()),
                    )
            old.append(
                container_defaults.DefaultsRecord(
                    container, record.access_policy_id, str(members.id), record.admins_group_id
                )
            )
    async with nexus_db() as db:
        for record in old:
            await SqlDefaultsStore(db).put(record)
        await db.commit()
    container_defaults.CONTAINER_DEFAULTS.forget_grouped()
    nexus.iam.invalidate()


async def _upgrade_role_features_world(nexus, nexus_db) -> None:
    """``role_features_test``'s world moved as far as #1585 left it, then its records
    taken back to before #1585."""
    nexus.iam.bootstrap()
    nexus.iam.invalidate()
    async with nexus_db() as db:
        await features_world._previous_database(db, nexus)
        assert await role_features.migrate_role_features(db, features_world.FLAGS)
        for name in (policy_tree.MIGRATION_NAME, container_names.MIGRATION_NAME):
            await db.execute(
                text(
                    "INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, '{}')"
                ),
                {"n": name, "at": features_world.NOW},
            )
        await db.commit()
    nexus.rewrite()
    async with nexus_db() as db:
        await container_defaults.migrate(db)
    await _before_1585(nexus, nexus_db)


def _features_matrix(nexus, users) -> dict:
    found = _matrix(nexus, users, world=_FeaturesWorld)
    return found


class _FeaturesWorld:
    WORKSPACES = features_world.WORKSPACES
    KNOWN_FEATURE_KEYS = features_world.KNOWN_FEATURE_KEYS


@pytest.mark.asyncio
async def test_a_store_from_before_the_groups_moves_and_reports_each_change(nexus_db):
    nexus = features_world._previous(features_world._world())
    users = [u for u in features_world.USERS if u != "ivan"]
    with nexus.installed():
        await _upgrade_role_features_world(nexus, nexus_db)
        before = _features_matrix(nexus, users)
        # The previous state holds what the move has to keep.
        assert before[("bob", "ws-a", "feature", "graph")]
        assert before[("henry", "org-1", "read", "organization")]
        report = await _move(nexus_db, nexus)
        assert report is not None and report.applied
        after = _features_matrix(nexus, users)
        changed = _diff(before, after)
        _check_report(report, changed, before["names"])
        assert not [k for k in changed if k[0] == "root"]
        # frank, a viewer of ws-a whose "Features of viewer" gave chat, is a Viewer:
        # chat goes, named.
        assert changed[("frank", "ws-a", "feature", "chat")] is False
        assert ("frank", "viewer_features") in {(c.user_id, c.reason) for c in report.changes}
        # Everyone else keeps the features their role's gave, now the offers'.
        lost = [k for k, v in changed.items() if k[2] == "feature" and not v and k[0] != "frank"]
        assert lost == []
        # The old records are converted, their "<X> members" retired, and
        # "Features of <role>" with them.
        assert len(report.converted_records) == 6
        assert len(report.retired_groups) == 6
        assert any(p.startswith("Features of ") for p in report.retired_policies)
        ws_a = workspace_container("org-1", "ws-a")
        assert ws_a in report.converted_ceilings
        with as_service_account("engine"):
            left = [p for p in nexus.iam._all_policies() if p.name.startswith("Features of ")]
            # Only those a pending invitation or a group still carries (the group
            # "team", holding builtin.member at ws-b) stay, listed; no person holds one.
            assert left
            for policy in left:
                holders = [a.principal_id for a in nexus.iam.list_attachments(policy_id=policy.id)]
                assert not [h for h in holders if container_defaults.is_user(h)]
                assert holders or nexus.iam.list_pending_grants(policy_id=policy.id)
                assert any(k.startswith(f"{policy.name} (") for k in report.kept_policies)
            groups = {
                g.name for g in access_model._pages(nexus.iam.list_groups) if g.status != "deleted"
            }
            assert not [g for g in groups if g.endswith(" members")]
            records = {r.container: r for r in await _defaults(nexus_db)}
            for record in records.values():
                assert container_defaults.grouped(nexus.iam, record)
            offer = nexus.iam.get_policy(records[ws_a].access_policy_id).document
            assert in_offer_form(offer)
        # The ceiling's Deny became the offer's absence: B is not offered at ws-a.
        with use_call_context(NexusIam.context("bob")):
            b = f"{ws_a}/module:agent/acme.people/B"
            assert not nexus.iam.authorize("module:UseAgent", b).allowed
        # A level is global: carol, a viewer of ws-a and an admin of ws-b, is a Member.
        reasons = {(c.user_id, c.reason) for c in report.changes}
        assert ("carol", "level_global") in reasons or ("carol", "level_features") in reasons
        with as_service_account("engine"):
            levels = LEVELS.get(nexus.iam)
            assert nexus.principal("carol") in nexus.iam.list_group_members(levels.members)
            # henry, a member of org-1 and of no workspace, is in "<O> people".
            org_people = records[org_container("org-1")].members_group_id
            assert nexus.principal("henry") in nexus.iam.list_group_members(org_people)
        assert any(o.startswith("henry in ") for o in report.org_only)
        assert ("henry", "org-1", "read", "organization") not in changed


@pytest.mark.asyncio
async def test_a_copy_the_sets_move_made_of_features_of_admin_goes_and_offers_nothing(nexus_db):
    """The sets' move copied an org-wide "Features of admin" into each workspace
    (``policy_tree``: its name, "What <id>, attached at <scope>, granted in <place>"):
    one per workspace for each org admin. The move retires it like the others, but
    what it gave is the org admin's, not a choice for the workspace's people: it
    adds nothing to the workspace's offer."""
    nexus = features_world._previous(features_world._world())
    with nexus.installed():
        await _upgrade_role_features_world(nexus, nexus_db)
        ws_c = workspace_container("org-2", "ws-c")
        containers = [r.container for r in await _defaults(nexus_db)]
        with as_service_account("engine"):
            iam = nexus.iam
            chosen = access_model.chosen_features(iam, containers)
            gina = nexus.principal("gina")
            copy = iam.create_policy(
                "Features of admin",
                parse_policy_document(
                    {
                        "version": POLICY_VERSION,
                        "statements": [
                            {
                                "sid": "UseFeatures",
                                "effect": "Allow",
                                "actions": ["nexus:UseFeature"],
                                "resources": [
                                    f"${{scope}}/nexus:feature/{key}"
                                    for key in features_world.KNOWN_FEATURE_KEYS
                                ],
                            }
                        ],
                    }
                ),
                description=(
                    f"What pol_org_2_admin_features, attached at {org_container('org-2')}/*, "
                    f"granted in {ws_c}: its modules and features within that place's "
                    "access." + policy_tree.MADE
                ),
                scope=ws_c,
            )
            iam.attach_policy(copy.id, gina, ws_c)
            assert access_model.is_retired_kind(copy) is not None
            assert access_model.chosen_features(iam, containers) == chosen
        report = await _move(nexus_db, nexus)
        assert report is not None and report.applied
        assert not [k for k in report.kept_attachments if "Features of admin" in k]
        with as_service_account("engine"):
            assert not nexus.iam.list_attachments(policy_id=copy.id)
            assert copy.id not in {p.id for p in nexus.iam._all_policies()}


@pytest.mark.asyncio
async def test_the_org_member_role_of_who_only_reached_it_through_a_workspace_goes(nexus_db):
    nexus = features_world._previous(features_world._world())
    with nexus.installed():
        # bob, a member of ws-a, also holds org-1's Member role, never invited to it.
        nexus.grant("bob", "member", nexus.org("org-1"))
        await _upgrade_role_features_world(nexus, nexus_db)
        report = await _move(nexus_db, nexus)
        assert report is not None
        assert any(r.startswith("bob at ") for r in report.org_roles_removed)
        assert not any(r.startswith("henry at ") for r in report.org_roles_removed)
        with as_service_account("engine"):
            bob = nexus.principal("bob")
            assert not [
                a
                for a in nexus.iam.list_attachments(principal_id=bob)
                if a.policy_id in ROLE_POLICIES
            ]
        records = {r.container: r for r in await _defaults(nexus_db)}
        with as_service_account("engine"):
            org_people = records[org_container("org-1")].members_group_id
            assert bob not in nexus.iam.list_group_members(org_people)

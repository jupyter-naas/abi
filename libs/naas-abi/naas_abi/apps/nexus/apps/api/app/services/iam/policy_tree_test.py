"""The sets and the workspace toggles become a tree of policies, on a database at
the previous state: IAM holding its sets (``iam_scope_sets``) and roles that held
every module scope, Nexus holding what each workspace turned off. For every
user, workspace, module item and feature, the decision is the same before and
after the move (the oracle below is the previous version's rule: the policies,
within the sets of the org and the workspace unless the user is a platform
admin, minus what the workspace turned off), on the memory, SQLite and
PostgreSQL stores; the only change is the platform admin reaching what a
workspace had turned off (``policy_tree.NOTES``).

The previous state is in the grammar before container paths
(``testing.LegacyNexusIam``), which this move reads and writes. An upgrade runs
it, then the move of the names (``container_names``), as a start does: the
decisions before are asked on the old names, those after on the same resources
named as paths."""

from __future__ import annotations

import json
import os
from datetime import datetime
from uuid import uuid4

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.iam import container_names, policy_tree
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.iam.legacy_names import NO_ORG
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    nexus_resource,
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree import (
    Legacy,
    TurnedOff,
    scope_within,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import (
    LegacyNexusIam,
    NexusIam,
    store_old_roles,
)
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    use_call_context,
)
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.IAMPorts import LegacyScopeSet
from naas_abi_core.services.iam.module_scopes import module_catalog
from naas_abi_core.services.iam.names import PLATFORM, is_old_scope, matches
from naas_abi_core.services.iam.policy import PolicyDocument, Statement
from sqlalchemy import text

NOW = datetime(2026, 1, 1)
FEATURES = ["chat", "files", "graph", "maps", "settings"]
FLAGS = FeatureFlagsConfig(enabled_features=FEATURES, role_baseline={})
DECLARED = {
    "version": 1,
    "resource_types": [{"name": "report", "id": "path"}],
    "actions": [
        {"name": "ExportReport", "level": "read", "resource_types": ["report"]},
        {"name": "DeleteReport", "level": "admin", "resource_types": ["report"]},
    ],
}
WORKSPACES = {"ws-a": "org-1", "ws-b": "org-1", "ws-c": "org-2", "ws-d": None}
# What modules expose: (type, module, name).
ITEMS = [
    ("agent", "acme.people", "A"),
    ("agent", "acme.people", "B"),
    ("agent", "acme.people", "X"),
    ("agent", "acme.crm", "Closer"),
    ("app", "acme.market", "prices"),
    ("app", "acme.market", "charts"),
    ("app", "acme.people", "directory"),
    ("workflow", "acme.crm", "sync"),
    ("pipeline", "acme.crm", "load"),
]
# The sets as the Modules & features pages recorded them.
SETS = {
    ("org-1", "-"): Legacy(
        ("acme.people", "app/acme.market/*", "workflow/*/*"), ("chat", "files", "settings")
    ),
    ("org-1", "ws-a"): Legacy(
        ("agent/acme.people/A", "agent/acme.people/B", "app/acme.market/*"), None
    ),
    ("org-2", "ws-c"): Legacy(None, ("chat", "settings")),
}
# What each workspace turned off: apps were off unless turned on.
TOGGLES = {
    "ws-a": TurnedOff(
        apps_on=frozenset({("acme.market", "prices")}),
        agents_off=frozenset({("acme.people", "B")}),
        custom_off=frozenset({"custom-off"}),
    ),
    "ws-b": TurnedOff(
        apps_on=frozenset({("acme.market", "prices"), ("acme.market", "charts")}),
        processes_off=frozenset({("workflow", "acme.crm", "sync")}),
    ),
    "ws-c": TurnedOff(apps_on=frozenset({("acme.people", "directory")})),
    "ws-d": TurnedOff(),
}
USERS = (
    "alice",  # owner of org-1 (org-wide too)
    "bob",  # admin of ws-a
    "carol",  # member of ws-a, ws-a's policy: every module item and feature
    "dave",  # member of ws-b, org-1's policy attached there: agents and graphs
    "erin",  # member of ws-c, a platform policy attached unscoped, with a Deny
    "frank",  # viewer of ws-b, in ws-a's group holding builtin.admin, org-1's group org-wide
    "gina",  # admin of org-2 (org-wide too)
    "henry",  # owner of ws-d, a workspace with no organization
    "ivan",  # member of ws-b and nothing else
    "jack",  # member of ws-b, ws-b's policy "Full access": * on everything there
    "kate",  # member of ws-a, ws-a's policy: nexus:* there
    "root",  # the platform admin
)
# Agents ws-a built itself (no module): one turned off, one on.
CUSTOM_AGENTS = {"custom-off": False, "custom-on": True}
ACTION_OF = {
    "agent": "module:UseAgent",
    "app": "module:OpenApp",
    "workflow": "module:RunWorkflow",
    "pipeline": "module:RunPipeline",
}


# -- the previous state ----------------------------------------------------------------


def _old_roles(nexus: LegacyNexusIam) -> None:
    """What the previous roles held beside the rest: admins and owners every
    module scope at their scope. On the old roles: registering the catalogs
    above regenerated them in the grammar of today."""
    store_old_roles(nexus.iam)
    store = nexus.iam.store
    extra = [
        Statement(
            "Allow",
            (f"{c.service}:*",),
            tuple(f"${{scope}}:{c.service}:{t.name}/*" for t in c.resource_types if t.module_scope),
            sid=f"OldModuleScopes{c.service}",
        )
        for c in nexus.iam.catalogs.all()
        if any(t.module_scope for t in c.resource_types)
    ]
    for role in (roles.ADMIN, roles.OWNER):
        policy = store.get_policy(role)
        store.put_managed_policy(
            policy.__class__(
                id=policy.id,
                name=policy.name,
                description=policy.description,
                document=PolicyDocument(statements=(*policy.document.statements, *extra)),
                managed=True,
            )
        )
    nexus.iam.invalidate()


def _policy(name: str, statements: list[Statement]) -> PolicyDocument:
    return PolicyDocument(statements=tuple(statements))


def _world(store=None) -> LegacyNexusIam:
    nexus = LegacyNexusIam(FLAGS, store=store)
    iam = nexus.iam
    with as_service_account("engine"):
        iam.register_catalog(module_scopes.CATALOG)
        iam._register_catalog(module_catalog(DECLARED, "acme.people"))
    scopes = {ws: nexus.workspace(org, ws) for ws, org in WORKSPACES.items()}
    nexus.org("org-1")
    nexus.org("org-2")
    nexus.grant("alice", "owner", nexus.org("org-1"))
    nexus.grant("bob", "admin", scopes["ws-a"])
    nexus.grant("carol", "member", scopes["ws-a"])
    nexus.grant("dave", "member", scopes["ws-b"])
    nexus.grant("erin", "member", scopes["ws-c"])
    nexus.grant("gina", "admin", nexus.org("org-2"))
    nexus.grant("henry", "owner", scopes["ws-d"])
    nexus.grant("ivan", "member", scopes["ws-b"])
    nexus.grant("jack", "member", scopes["ws-b"])
    nexus.grant("kate", "member", scopes["ws-a"])
    nexus.grant("frank", "viewer", scopes["ws-b"])
    nexus.platform_admin("root")
    with as_service_account("engine"):
        # ws-a's own policy: every module item and feature, as the builder wrote it.
        everything = iam.create_policy(
            "Everything here",
            _policy(
                "",
                [
                    Statement("Allow", ("module:*",), ("${scope}:module:*",)),
                    Statement("Allow", ("acme_people:*",), ("${scope}:acme_people:*",)),
                    Statement("Allow", ("nexus:UseFeature",), ("${scope}:nexus:feature/*",)),
                ],
            ),
            scope=scopes["ws-a"],
        )
        iam.attach_policy(everything.id, nexus.principal("carol"), scopes["ws-a"])
        # org-1's policy, mixed: agents (bounded) and graphs (not), attached at ws-b.
        analysts = iam.create_policy(
            "Analysts",
            _policy(
                "",
                [
                    Statement(
                        "Allow",
                        ("module:UseAgent", "triple_store:Query"),
                        ("${scope}:module:agent/*", "${scope}:triple_store:graph/*"),
                    ),
                    Statement("Allow", ("nexus:UseFeature",), ("${scope}:nexus:feature/graph",)),
                ],
            ),
            scope="abi:org-1:-",
        )
        iam.attach_policy(analysts.id, nexus.principal("dave"), scopes["ws-b"])
        # A platform policy attached unscoped: acme.people's agents everywhere, but X.
        people = iam.create_policy(
            "People agents everywhere",
            _policy(
                "",
                [
                    Statement(
                        "Allow",
                        ("module:UseAgent", "nexus:UseFeature"),
                        ("abi:*:*:module:agent/acme.people/*", "abi:*:*:nexus:feature/chat"),
                    ),
                    Statement(
                        "Deny", ("module:UseAgent",), ("abi:*:*:module:agent/acme.people/X",)
                    ),
                ],
            ),
        )
        iam.attach_policy(people.id, nexus.principal("erin"))
        # Groups: ws-a's holding the admin role, org-1's holding Analysts org-wide.
        admins = nexus.group("ws-a admins", scopes["ws-a"])
        iam.attach_policy(roles.ADMIN, admins, scopes["ws-a"])
        nexus.add_member(admins, nexus.principal("frank"))
        org_group = nexus.group("org analysts", "abi:org-1:-")
        iam.attach_policy(analysts.id, org_group, "abi:org-1:*")
        nexus.add_member(org_group, nexus.principal("frank"))
        # A service account: admin of ws-a, never bounded by a set, and in a
        # platform group holding Analysts org-wide.
        bot = iam.create_service_account("ci/bot")
        iam.attach_policy(roles.ADMIN, bot.id, scopes["ws-a"])
        ops = nexus.group("ops")  # a platform group: service accounts may join
        iam.attach_policy(analysts.id, ops, "abi:org-1:*")
        nexus.add_member(ops, bot.id)
        # "Full access" in ws-b (every action of every service) and nexus:* in ws-a:
        # split, what is not a module scope or a feature spelled out.
        full = iam.create_policy(
            "Full access",
            _policy("", [Statement("Allow", ("*",), ("${scope}:*",), sid="All")]),
            scope=scopes["ws-b"],
        )
        iam.attach_policy(full.id, nexus.principal("jack"), scopes["ws-b"])
        everything_nexus = iam.create_policy(
            "Nexus",
            _policy("", [Statement("Allow", ("nexus:*",), ("${scope}:nexus:*",))]),
            scope=scopes["ws-a"],
        )
        iam.attach_policy(everything_nexus.id, nexus.principal("kate"), scopes["ws-a"])
        # Invitations pending: an admin of ws-a, an owner of org-1.
        iam.create_pending_grant("builtin", "zoe@example.com", roles.ADMIN, scopes["ws-a"])
        iam.create_pending_grant("builtin", "olga@example.com", roles.OWNER, "abi:org-1:-")
    _old_roles(nexus)
    _seed_legacy_sets(nexus)
    return nexus


def _seed_legacy_sets(nexus: LegacyNexusIam) -> None:
    rows = [LegacyScopeSet(org, ws, s.modules, s.features) for (org, ws), s in SETS.items()]
    store = nexus.iam.store
    if hasattr(store, "seed_legacy_scope_sets"):
        store.seed_legacy_scope_sets(rows)
        return
    schema = getattr(store, "schema", None)
    table = f'"{schema}".iam_scope_sets' if schema else "iam_scope_sets"
    with store._engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {table} (org VARCHAR(64) NOT NULL, "
                "workspace VARCHAR(64) NOT NULL, modules TEXT, features TEXT, "
                "PRIMARY KEY (org, workspace))"
            )
        )
        for row in rows:
            conn.execute(
                text(f"INSERT INTO {table} VALUES (:o, :w, :m, :f)"),
                {
                    "o": row.org,
                    "w": row.workspace,
                    "m": None if row.modules is None else json.dumps(list(row.modules)),
                    "f": None if row.features is None else json.dumps(list(row.features)),
                },
            )


async def _previous_database(db) -> None:
    await db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) PRIMARY KEY, "
            "applied_at TIMESTAMP, report TEXT)"
        )
    )
    for name in policy_tree.AFTER:
        await db.execute(
            text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, '{}')"),
            {"n": name, "at": NOW},
        )
    for org in ("org-1", "org-2"):
        db.add(
            OrganizationModel(
                id=org, name=org.upper(), slug=org, owner_id="alice", created_at=NOW, updated_at=NOW
            )
        )
    for ws, org in WORKSPACES.items():
        db.add(
            WorkspaceModel(
                id=ws,
                name=f"Workspace {ws}",
                slug=ws,
                owner_id="alice",
                organization_id=org,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    await db.flush()
    await db.execute(text("DROP TABLE IF EXISTS workflow_visibility"))
    await db.execute(
        text(
            "CREATE TABLE workflow_visibility (workspace_id VARCHAR(255) NOT NULL, "
            "type VARCHAR(32) NOT NULL, module_id VARCHAR(255) NOT NULL, name VARCHAR(255) "
            "NOT NULL, enabled BOOLEAN NOT NULL DEFAULT TRUE, updated_at TIMESTAMP, "
            "PRIMARY KEY (workspace_id, type, module_id, name))"
        )
    )
    # The toggles' columns, as migrations 0028 and the agents' made them.
    await db.execute(
        text("ALTER TABLE app_configs ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT TRUE")
    )
    await db.execute(
        text("ALTER TABLE agent_configs ADD COLUMN enabled INTEGER NOT NULL DEFAULT 0")
    )
    await db.execute(text("DELETE FROM app_configs"))
    for ws, toggles in TOGGLES.items():
        for module, name in sorted(toggles.apps_on):
            await db.execute(
                text(
                    "INSERT INTO app_configs (id, workspace_id, app_id, enabled, created_at, "
                    "updated_at) VALUES (:id, :ws, :app, 1, :at, :at)"
                ),
                {"id": uuid4().hex, "ws": ws, "app": f"{module}:{name}", "at": NOW},
            )
        for module, name in sorted(toggles.agents_off):
            await db.execute(
                text(
                    "INSERT INTO agent_configs (id, workspace_id, name, class_name, provider, is_default, "
                    "enabled, created_at, updated_at) VALUES (:id, :ws, :n, :c, 'remote', 0, 0, "
                    ":at, :at)"
                ),
                {"id": uuid4().hex, "ws": ws, "n": name, "c": f"{module}/{name}", "at": NOW},
            )
        for kind, module, name in sorted(toggles.processes_off):
            await db.execute(
                text("INSERT INTO workflow_visibility VALUES (:ws, :t, :m, :n, 0, :at)"),
                {"ws": ws, "t": kind, "m": module, "n": name, "at": NOW},
            )
    for agent_id, on in CUSTOM_AGENTS.items():
        await db.execute(
            text(
                "INSERT INTO agent_configs (id, workspace_id, name, is_default, enabled, "
                "created_at, updated_at) VALUES (:id, 'ws-a', :id, 0, :on, :at, :at)"
            ),
            {"id": agent_id, "on": int(on), "at": NOW},
        )
    # A row turned on hides nothing.
    await db.execute(
        text(
            "INSERT INTO agent_configs (id, workspace_id, name, class_name, provider, "
            "is_default, enabled, created_at, updated_at) VALUES (:id, 'ws-a', 'A', "
            "'acme.people/A', 'remote', 0, 1, :at, :at)"
        ),
        {"id": uuid4().hex, "at": NOW},
    )
    await db.commit()


REAL_RESOLVER = policy_tree._agent_resolver


@pytest.fixture(autouse=True)
def _remote_agents(monkeypatch):
    """Agent rows name remote agents (``<module>/<name>``): no engine registry."""
    from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import split_key

    def resolver():
        def resolve(class_name, provider, *, strict=False):
            module, name = split_key(class_name)
            return ModuleScope("agent", module, name)

        return resolve

    monkeypatch.setattr(policy_tree, "_agent_resolver", resolver)


# -- decisions -----------------------------------------------------------------------------


def _old(ws: str, rest: str) -> str:
    """A name in a workspace, in the grammar before container paths."""
    return f"abi:{WORKSPACES[ws] or NO_ORG}:{ws}:{rest}"


def _new(ws: str, rest: str) -> str:
    """The same name as a path: in the workspace's container."""
    return f"{workspace_container(WORKSPACES[ws], ws)}/{rest}"


def _names(named=_old) -> dict[tuple[str, str, str], tuple[str, str]]:
    """``(workspace, kind, item) -> (action, resource)`` for every module item,
    declared action and feature, in every workspace; named with ``named`` (``_old``
    before the upgrade, ``_new`` after)."""
    found: dict[tuple[str, str, str], tuple[str, str]] = {}
    for ws in WORKSPACES:
        for type_name, module, name in ITEMS:
            resource = named(ws, f"module:{type_name}/{module}/{name}")
            found[(ws, type_name, f"{module}/{name}")] = (ACTION_OF[type_name], resource)
            if type_name in module_scopes.RUNS_ACTION:
                action = f"module:{module_scopes.RUNS_ACTION[type_name]}"
                found[(ws, f"{type_name}-runs", f"{module}/{name}")] = (action, resource)
        for action in ("acme_people:ExportReport", "acme_people:DeleteReport"):
            found[(ws, "declared", action)] = (action, named(ws, "acme_people:report/q3"))
        for key in FEATURES:
            found[(ws, "feature", key)] = ("nexus:UseFeature", named(ws, f"nexus:feature/{key}"))
    for agent_id in CUSTOM_AGENTS:
        found[("ws-a", "custom", agent_id)] = (
            "nexus:UseAgent",
            named("ws-a", f"nexus:agent/{agent_id}"),
        )
    return found


def test_the_names_after_are_the_names_of_today():
    """``_new`` names what Nexus and core name today."""
    w = workspace_container("org-1", "ws-a")
    assert _new("ws-a", "module:agent/acme.people/A") == module_scopes.scope_resource(
        "agent", "acme.people", "A", container=w
    )
    assert _new("ws-a", "nexus:feature/chat") == nexus_resource("feature", container=w, id="chat")
    assert _new("ws-a", "nexus:agent/custom-on") == nexus_resource(
        "agent", container=w, id="custom-on"
    )
    assert _new("ws-d", "nexus:feature/chat").startswith("abi:nexus:workspace/ws-d/")


def _context(subject: str, nexus: LegacyNexusIam) -> CallContext:
    if subject.startswith("sa:"):
        return CallContext(principal=Principal(id=subject[3:], kind="service_account"))
    return NexusIam.context(subject)


def _iam_decisions(nexus: LegacyNexusIam, subjects) -> dict[tuple, bool]:
    """IAM's decisions on the names of the grammar the world is in."""
    found: dict[tuple, bool] = {}
    names = _names(_new if nexus.rewritten else _old)
    for subject in subjects:
        with use_call_context(_context(subject, nexus)):
            for key, (action, resource) in names.items():
                found[(subject, *key)] = nexus.iam.authorize(action, resource).allowed
    return found


def _sets_allow(ws: str, kind: str, item: str, action: str) -> bool:
    """The previous version's rule (core ``sets.allows``)."""
    org = WORKSPACES[ws] or NO_ORG
    for found in (SETS.get((org, "-")), SETS.get((org, ws))):
        if found is None:
            continue
        if kind == "feature":
            if found.features is not None and item not in found.features:
                return False
            continue
        if found.modules is None:
            continue
        if kind == "declared":
            service = action.partition(":")[0]
            if not (
                "acme.people" in found.modules
                or action in found.modules
                or f"{service}:*" in found.modules
                or "*:*" in found.modules
            ):
                return False
            continue
        module, name = item.split("/", 1)
        if not scope_within(found.modules, kind.removesuffix("-runs"), module, name):
            return False
    return True


def _turned_off(ws: str, kind: str, item: str) -> bool:
    toggles = TOGGLES.get(ws, TurnedOff())
    if kind == "custom":
        return item in toggles.custom_off
    if kind in ("feature", "declared") or kind.endswith("-runs"):
        return False
    module, name = item.split("/", 1)
    if kind == "app":
        return (module, name) not in toggles.apps_on
    if kind == "agent":
        return (module, name) in toggles.agents_off
    return (kind, module, name) in toggles.processes_off


def _before(nexus: LegacyNexusIam, subjects) -> dict[tuple, bool]:
    raw = _iam_decisions(nexus, subjects)
    found: dict[tuple, bool] = {}
    for key, allowed in raw.items():
        subject, ws, kind, item = key
        action = _names()[(ws, kind, item)][0]
        unbounded = subject == "root" or subject.startswith("sa:")
        bounded_kind = kind != "custom"  # the sets bounded module scopes and features
        if allowed and bounded_kind and not unbounded and not _sets_allow(ws, kind, item, action):
            allowed = False
        if allowed and _turned_off(ws, kind, item):
            # Nexus refused what a workspace turned off to every caller: users, the
            # platform admin, service accounts.
            allowed = False
        found[key] = allowed
    return found


def _subjects(nexus: LegacyNexusIam) -> list[str]:
    with as_service_account("engine"):
        bot = nexus.iam.find_service_account("ci/bot").id
    return [*USERS, f"sa:{bot}"]


async def _upgrade(
    nexus: LegacyNexusIam, nexus_db, *, names: bool = True
) -> policy_tree.Report | None:
    """A start on this version: the engine's (the roles are regenerated, in the
    grammar of today, and hold no module scope), then Nexus's moves, the sets'
    and (``names``) the move of the names, which waits for it."""
    with as_service_account("engine"):
        nexus.iam._refresh_builtin_policies()
    nexus.iam.invalidate()
    async with nexus_db() as db:
        await _previous_database(db)
        report = await policy_tree.migrate_sets(db)
        if names:
            await _rewrite(nexus, db)
    nexus.iam.invalidate()
    return report


async def _rewrite(nexus: LegacyNexusIam, db) -> container_names.Report | None:
    """The move of the names, as a start makes it (Nexus's organizations and
    workspaces read from its tables); None while it waits."""
    report = await container_names.migrate_names(db)
    if report is not None:
        nexus.rewritten = True
        nexus.iam.invalidate()
    return report


def _expected_changes(before: dict[tuple, bool]) -> dict[tuple, bool]:
    """What changes by construction (``NOTES``): the platform admin reaches what
    a workspace had turned off."""
    return {
        key: True
        for key, allowed in before.items()
        if key[0] == "root" and not allowed and _turned_off(*key[1:])
    }


# -- the tests ---------------------------------------------------------------------------------


async def _check_upgrade(nexus: LegacyNexusIam, nexus_db) -> None:
    subjects = _subjects(nexus)
    before = _before(nexus, subjects)
    # The previous state is not empty: the move has something to keep.
    assert before[("bob", "ws-a", "agent", "acme.people/A")]
    assert not before[("bob", "ws-a", "agent", "acme.people/B")]  # turned off
    assert not before[("bob", "ws-a", "agent", "acme.people/X")]  # outside ws-a's set
    assert before[("bob", "ws-a", "app", "acme.market/prices")]
    assert not before[("bob", "ws-a", "app", "acme.market/charts")]  # never turned on
    assert before[("alice", "ws-b", "app", "acme.market/charts")]
    assert not before[("alice", "ws-b", "workflow", "acme.crm/sync")]
    assert before[("alice", "ws-b", "workflow-runs", "acme.crm/sync")]
    assert not before[("alice", "ws-b", "agent", "acme.crm/Closer")]  # outside org-1's
    assert before[("carol", "ws-a", "feature", "chat")]
    assert not before[("carol", "ws-a", "feature", "graph")]  # outside org-1's
    assert before[("dave", "ws-b", "agent", "acme.people/X")]
    assert before[("erin", "ws-c", "agent", "acme.people/A")]
    assert not before[("erin", "ws-c", "agent", "acme.people/X")]  # its own Deny
    assert before[("erin", "ws-c", "feature", "chat")]
    assert before[("frank", "ws-a", "agent", "acme.people/A")]
    assert before[("gina", "ws-c", "agent", "acme.crm/Closer")]
    assert not before[("gina", "ws-c", "feature", "files")]
    assert before[("henry", "ws-d", "pipeline", "acme.crm/load")]
    assert before[("henry", "ws-d", "declared", "acme_people:ExportReport")]
    assert not any(v for k, v in before.items() if k[0] == "ivan")
    assert before[(subjects[-1], "ws-a", "agent", "acme.crm/Closer")]  # never bounded

    report = await _upgrade(nexus, nexus_db)

    assert report is not None and not policy_tree.pending()
    assert nexus.rewritten and not container_names.pending()
    after = _iam_decisions(nexus, subjects)
    changed = {k: v for k, v in after.items() if before[k] != v}
    assert changed == _expected_changes(before)
    # Non-module grants are kept: dave still queries ws-b's graphs.
    with use_call_context(NexusIam.context("dave")):
        assert nexus.iam.authorize(
            "triple_store:Query", _new("ws-b", "triple_store:graph/g1")
        ).allowed
    # What the sets were is policies now, and IAM's sets are gone.
    with as_service_account("engine"):
        assert nexus.iam.legacy_scope_sets() == []
        names = {p.name for p in nexus.iam._all_policies()}
    assert {"ORG-1 access", "ORG-2 access", "Workspace ws-a access"} <= names
    # Every policy is owned by a container of today, those made for the
    # workspace in no organization by the platform.
    with as_service_account("engine"):
        owners = {p.name: p.owner_scope for p in nexus.iam._all_policies()}
    assert not [o for o in owners.values() if is_old_scope(o)]
    assert owners["Workspace ws-d access"] == PLATFORM


@pytest.mark.asyncio
async def test_nobody_gains_or_loses_access(nexus_db):
    nexus = _world()
    with nexus.installed():
        await _check_upgrade(nexus, nexus_db)


@pytest.mark.asyncio
async def test_nobody_gains_or_loses_access_on_sqlite(nexus_db, tmp_path):
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import IAMStoreSQLite

    nexus = _world(IAMStoreSQLite(str(tmp_path / "iam.sqlite")))
    with nexus.installed():
        await _check_upgrade(nexus, nexus_db)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nobody_gains_or_loses_access_on_postgresql(nexus_db):
    dsn = os.environ.get("IAM_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set IAM_TEST_POSTGRES_DSN to run on PostgreSQL")
    from naas_abi_core.services.iam.adapters.secondary.IAMStorePostgreSQL import (
        IAMStorePostgreSQL,
        sqlalchemy_url,
    )
    from sqlalchemy import create_engine

    schema = f"iam_test_{uuid4().hex[:12]}"
    store = IAMStorePostgreSQL(dsn, schema)
    try:
        nexus = _world(store)
        with nexus.installed():
            await _check_upgrade(nexus, nexus_db)
    finally:
        store.close()
        engine = create_engine(sqlalchemy_url(dsn))
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()


@pytest.mark.asyncio
async def test_once_and_again_changes_nothing(nexus_db):
    nexus = _world()
    with nexus.installed():
        await _upgrade(nexus, nexus_db)
        with as_service_account("engine"):
            policies = {(p.id, p.revision) for p in nexus.iam._all_policies()}
            attachments = {a.id for a in nexus.iam.list_attachments()}
        async with nexus_db() as db:
            assert await policy_tree.migrate_sets(db) is None
            assert await container_names.migrate_names(db) is None
        with as_service_account("engine"):
            assert {(p.id, p.revision) for p in nexus.iam._all_policies()} == policies
            assert {a.id for a in nexus.iam.list_attachments()} == attachments


@pytest.mark.asyncio
async def test_an_interrupted_move_plans_the_same_again(nexus_db, monkeypatch):
    """A start that fails half way records nothing, keeps module scopes and
    features refused, and the next start finishes with the same result."""
    nexus = _world()
    with nexus.installed():
        subjects = _subjects(nexus)
        before = _before(nexus, subjects)
        real = nexus.iam.attach_policy
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 5:
                raise RuntimeError("the store went away")
            return real(*args, **kwargs)

        monkeypatch.setattr(nexus.iam, "attach_policy", flaky)
        assert await _upgrade(nexus, nexus_db) is None
        # The names wait for the sets: nothing rewritten, both still refused.
        assert policy_tree.pending() and container_names.pending()
        assert not nexus.rewritten
        monkeypatch.setattr(nexus.iam, "attach_policy", real)
        async with nexus_db() as db:
            assert await policy_tree.migrate_sets(db) is not None
            assert await _rewrite(nexus, db) is not None
        nexus.iam.invalidate()
        after = _iam_decisions(nexus, subjects)
        assert {k: v for k, v in after.items() if before[k] != v} == _expected_changes(before)


@pytest.mark.asyncio
async def test_a_case_it_cannot_keep_stops_the_move(nexus_db, caplog):
    """A sub-policy granting module scopes cannot be moved under an access
    policy without losing its own parent: nothing is recorded, the refusal is
    named, and module scopes and features stay refused."""
    nexus = _world()
    with nexus.installed():
        with as_service_account("engine"):
            parent = nexus.iam.create_policy(
                "Parent",
                _policy("", [Statement("Allow", ("module:*",), ("${scope}:module:*",))]),
                scope="abi:org-1:ws-a",
            )
            nexus.iam.create_policy(
                "Child",
                _policy(
                    "", [Statement("Allow", ("module:UseAgent",), ("${scope}:module:agent/*",))]
                ),
                scope="abi:org-1:ws-a",
                parent=parent.id,
            )
        assert await _upgrade(nexus, nexus_db) is None
        assert policy_tree.pending() and container_names.pending()
        assert "Child" in caplog.text and "sub-policy" in caplog.text
        async with nexus_db() as db:
            recorded = (
                await db.execute(
                    text("SELECT 1 FROM iam_migrations WHERE name = :n"),
                    {"n": policy_tree.MIGRATION_NAME},
                )
            ).first()
        assert recorded is None
    policy_tree.set_pending(False)
    container_names.set_pending(False)


@pytest.mark.asyncio
async def test_pending_invitations_get_the_access_of_their_role(nexus_db):
    nexus = _world()
    with nexus.installed():
        await _upgrade(nexus, nexus_db)
        with as_service_account("engine"):
            by_name = {p.id: p.name for p in nexus.iam._all_policies()}
            pending = {
                (g.email, by_name.get(g.policy_id, g.policy_id), g.scope)
                for g in nexus.iam.list_pending_grants()
            }
    assert (
        "zoe@example.com",
        "Workspace ws-a modules (admins and owners)",
        workspace_container("org-1", "ws-a"),
    ) in pending
    # An org owner holds the role org-wide once signed in: every workspace too.
    assert (
        "olga@example.com",
        "ORG-1 modules (admins and owners)",
        org_container("org-1"),
    ) in pending
    assert (
        "olga@example.com",
        "Workspace ws-b modules (admins and owners)",
        workspace_container("org-1", "ws-b"),
    ) in pending


@pytest.mark.asyncio
async def test_removing_an_agent_from_an_org_access_removes_it_below_at_once(nexus_db):
    nexus = _world()
    with nexus.installed():
        await _upgrade(nexus, nexus_db)
        agent = _new("ws-a", "module:agent/acme.people/A")
        for user in ("bob", "carol"):
            with use_call_context(NexusIam.context(user)):
                assert nexus.iam.authorize("module:UseAgent", agent).allowed, user
        with as_service_account("engine"):
            org_access = next(p for p in nexus.iam._all_policies() if p.name == "ORG-1 access")
            narrowed = [
                Statement(
                    s.effect,
                    s.actions,
                    tuple(r for r in s.resources if "acme.people" not in r)
                    + (("${scope}/module:agent/acme.crm/*",) if s.sid == "Modules" else ()),
                    sid=s.sid,
                )
                for s in org_access.document.statements
                if s.resources
            ]
            nexus.iam.update_policy(
                org_access.id,
                expected_revision=org_access.revision,
                document=PolicyDocument(statements=tuple(s for s in narrowed if s.resources)),
            )
        for user in ("bob", "carol"):
            with use_call_context(NexusIam.context(user)):
                assert not nexus.iam.authorize("module:UseAgent", agent).allowed, user
        with use_call_context(NexusIam.context("root")):
            assert nexus.iam.authorize("module:UseAgent", agent).allowed


@pytest.mark.asyncio
async def test_an_admin_of_a_workspace_with_no_policy_uses_nothing(nexus_db):
    nexus = _world()
    with nexus.installed():
        await _upgrade(nexus, nexus_db)
        scope = nexus.workspace("org-1", "ws-new")
        nexus.grant("nora", "admin", scope)
        nexus.grant("owen", "owner", scope)
        for user in ("nora", "owen"):
            with use_call_context(NexusIam.context(user)):
                for type_name, module, name in ITEMS:
                    resource = module_scopes.scope_resource(
                        type_name, module, name, container=scope
                    )
                    assert not nexus.iam.authorize(ACTION_OF[type_name], resource).allowed
                assert not nexus.iam.authorize(
                    "acme_people:ExportReport", f"{scope}/acme_people:report/q3"
                ).allowed
                for key in FEATURES:
                    feature = nexus_resource("feature", container=scope, id=key)
                    assert not nexus.iam.authorize("nexus:UseFeature", feature).allowed


def test_a_pattern_within_a_place_is_exact():
    within = policy_tree.within_place
    assert within("abi:*:*:module:agent/*", "abi:o:w:") == ["module:agent/*"]
    assert within("abi:o:*:module:agent/a", "abi:o:w:") == ["module:agent/a"]
    assert within("abi:*", "abi:o:w:") == ["*"]
    assert within("abi:p:*:module:agent/a", "abi:o:w:") == []
    assert within("abi:-:-:module:agent/a", "abi:-:-:") == ["module:agent/a"]


def test_an_access_policy_says_what_the_set_said():
    statements = policy_tree.access_statements(
        Legacy(("acme.people", "agent/*/*", "acme_crm:Sync"), ("chat",)),
        {"acme_people": "acme.people", "acme_crm": "acme.crm"},
        turned_off=TurnedOff(
            apps_on=frozenset({("acme.people", "directory"), ("acme.market", "prices")}),
            agents_off=frozenset({("acme.people", "B")}),
        ),
    )
    by_sid = {s.sid: s for s in statements}
    modules = set(by_sid["Modules"].resources)
    assert "${scope}:module:agent/*" in modules
    assert "${scope}:module:workflow/acme.people/*" in modules
    # Apps were off unless turned on: only those, within the set.
    assert "${scope}:module:app/acme.people/directory" in modules
    assert not any("acme.market" in r for r in modules)
    assert by_sid["ActionsAcmePeople"].actions == ("acme_people:*",)
    assert by_sid["ActionsAcmeCrm"].actions == ("acme_crm:Sync",)
    assert by_sid["Features"].resources == ("${scope}:nexus:feature/chat",)
    assert by_sid["TurnedOffAgents"].effect == "Deny"


def test_a_set_of_nothing_lets_nothing_through():
    """An Allow no name matches: a parent bounding its sub-policies to nothing,
    and no Deny that would refuse a service account through a group."""
    statements = policy_tree.access_statements(Legacy((), ()), {})
    assert [(s.sid, s.effect) for s in statements] == [("Nothing", "Allow")]
    agent = "abi:o:w:module:agent/m/a"
    assert not any(
        matches(r.replace("${scope}", "abi:o:w"), agent) for r in statements[0].resources
    )


@pytest.mark.asyncio
async def test_module_scopes_and_features_are_refused_until_the_move(nexus_db):
    """Until the move is recorded nothing the sets bounded is let through: never
    wider than before the upgrade, the platform admin included."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
    from naas_abi.apps.nexus.apps.api.app.services.iam.user_features import user_feature_flags

    nexus = _world()

    async def refused() -> None:
        for user in ("bob", "root"):
            assert not await AUTHZ.allowed_scope(scope, user=user, workspace="ws-a")
            assert (
                await AUTHZ.filter_scopes(
                    [scope], user=user, workspace="ws-a", scope_of=lambda s: s
                )
                == []
            )
        flags = await user_feature_flags("root", [("org-1", "ws-a")], FEATURES)
        assert not any(flags["ws-a"].values())

    with nexus.installed():
        scope = ModuleScope("agent", "acme.people", "A")
        # As a start sets them before its moves.
        policy_tree.set_pending(True)
        container_names.set_pending(True)
        try:
            await refused()
            # The sets moved, the names not yet: still refused.
            await _upgrade(nexus, nexus_db, names=False)
            assert not policy_tree.pending() and container_names.pending()
            await refused()
            async with nexus_db() as db:
                assert await _rewrite(nexus, db) is not None
            assert not container_names.pending()
        finally:
            policy_tree.set_pending(False)
            container_names.set_pending(False)
        assert await AUTHZ.allowed_scope(scope, user="bob", workspace="ws-a")


@pytest.mark.asyncio
async def test_what_is_not_a_module_scope_or_a_feature_stays_as_it_was(nexus_db):
    """A "Full access" (``*``) and a ``nexus:*`` policy are split: what they
    grant beyond module scopes and features is spelled out, past 100 patterns
    in several statements, and still granted; the report names the wildcard."""
    nexus = _world()
    with nexus.installed():
        report = await _upgrade(nexus, nexus_db)
        assert report is not None
        with use_call_context(NexusIam.context("jack")):
            assert nexus.iam.authorize(
                "triple_store:Query", _new("ws-b", "triple_store:graph/g1")
            ).allowed
            assert nexus.iam.authorize(
                "nexus:UpdateWorkspace", workspace_container("org-1", "ws-b")
            ).allowed
        with use_call_context(NexusIam.context("kate")):
            assert nexus.iam.authorize(
                "nexus:UpdateWorkspace", workspace_container("org-1", "ws-a")
            ).allowed
        with as_service_account("engine"):
            full = next(p for p in nexus.iam._all_policies() if p.name == "Nexus")
        assert len(full.document.statements) > 1
        assert all(len(st.actions) <= 100 for st in full.document.statements)
        assert not any("nexus:UseFeature" in st.actions for st in full.document.statements)
    assert any("Full access" in n and "the bus" in n for n in report.notes)


@pytest.mark.asyncio
async def test_an_org_wide_grant_that_moved_is_named_in_the_report(nexus_db):
    """An org's policy attached org-wide is cut to the workspaces that exist:
    a workspace made later gets nothing from it, and the report says so."""
    nexus = _world()
    with nexus.installed():
        report = await _upgrade(nexus, nexus_db)
    assert any("Analysts" in n and "org-wide (abi:org-1:*)" in n for n in report.notes)
    async with nexus_db() as db:
        recorded = (
            await db.execute(
                text("SELECT report FROM iam_migrations WHERE name = :n"),
                {"n": policy_tree.MIGRATION_NAME},
            )
        ).scalar()
    assert any("Analysts" in n for n in json.loads(recorded)["notes"])


@pytest.mark.asyncio
async def test_a_turned_off_agent_the_workspace_built_stays_off(nexus_db):
    """Its row's switch refused it to everyone: after the upgrade a Deny does,
    for who held a role there; the one turned on is still used."""
    nexus = _world()
    with nexus.installed():
        await _upgrade(nexus, nexus_db)
        off = _new("ws-a", "nexus:agent/custom-off")
        on = _new("ws-a", "nexus:agent/custom-on")
        for user in ("bob", "carol", "alice", "frank"):
            with use_call_context(NexusIam.context(user)):
                assert not nexus.iam.authorize("nexus:UseAgent", off).allowed, user
                assert nexus.iam.authorize("nexus:UseAgent", on).allowed, user


def test_the_upgrade_waits_for_the_role_features_move_only():
    """Old feature policies kept as a sub-policy's parent are detached: their
    retirement is no reason to wait (it would wait for good)."""
    assert "role_features_retired_v1" not in policy_tree.AFTER
    assert "role_features_v1" in policy_tree.AFTER


def test_a_turned_off_agent_of_a_module_not_loaded_stops_the_move(monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary import (
        agents__primary_adapter__FastAPI as agents_api,
    )

    monkeypatch.setattr(agents_api, "_get_agent_class_registry", lambda: {})
    monkeypatch.setattr(agents_api, "agent_class_modules", lambda: {})
    resolve = REAL_RESOLVER()
    # Turned on: guessed as before, it denies nothing.
    assert resolve("acme.people.agents/Scout", None) is not None
    with pytest.raises(policy_tree.UpgradeStop, match="did not load"):
        resolve("acme.people.agents/Scout", None, strict=True)
    # A remote agent's name is its own: never guessed.
    assert resolve("acme.people/Scout", "remote", strict=True) is not None

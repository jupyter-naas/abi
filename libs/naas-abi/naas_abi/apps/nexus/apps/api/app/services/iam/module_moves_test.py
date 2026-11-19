"""The X app moved from the engine module to the remote one: what named it follows.

IAM's stored names (``module_moves``, at start) and Nexus's rows
(``migrations/0072_remote_x_app.sql``): whoever opened the X app in a workspace
before (``app/naas_abi_marketplace.applications.x/x_proxy``) opens it after
(``app/applications.x/x_proxy``), whoever did not still does not.
"""

from __future__ import annotations

import contextlib
import io
import json

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.services.apps.scopes import app_scope
from naas_abi.apps.nexus.apps.api.app.services.iam import container_names, module_moves
from naas_abi.apps.nexus.apps.api.app.services.iam.module_moves import MOVES, MovedScopes
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import IAMStoreSQLite
from naas_abi_core.services.iam.policy import MAX_PATTERNS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

OLD_APP_ID = "naas_abi_marketplace.applications.x:x_proxy"
NEW_APP_ID = "remote/applications.x:x_proxy"
# The id before the rename to x_proxy: nothing maps it, it is left.
OLDER_APP_ID = "naas_abi_marketplace.applications.x:x"
OLD = "module:app/naas_abi_marketplace.applications.x/x_proxy"
NEW = "module:app/applications.x/x_proxy"
OPEN = "module:OpenApp"


def test_the_move_is_the_x_apps_scopes() -> None:
    (move,) = MOVES
    assert move.old == OLD == app_scope(OLD_APP_ID).resource("abi:").removeprefix("abi:")
    assert move.new == NEW == app_scope(NEW_APP_ID).resource("abi:").removeprefix("abi:")


@pytest.mark.parametrize(
    ("pattern", "after"),
    [
        # Exactly the old app, whatever names its container: the new one instead.
        (f"${{scope}}/{OLD}", [f"${{scope}}/{NEW}"]),
        (f"abi:nexus:organization/o/*/{OLD}", [f"abi:nexus:organization/o/*/{NEW}"]),
        (f"abi:{OLD}", [f"abi:{NEW}"]),
        # Over the old module, not the new one: kept, the new app named beside it, alone.
        (
            "${scope}/module:app/naas_abi_marketplace.applications.x/*",
            ["${scope}/module:app/naas_abi_marketplace.applications.x/*", f"${{scope}}/{NEW}"],
        ),
        (
            "${scope}/module:*/naas_abi_marketplace.*",
            ["${scope}/module:*/naas_abi_marketplace.*", f"${{scope}}/{NEW}"],
        ),
        # Already reaching the new app, or never the old one: as they are.
        ("${scope}/module:app/*", ["${scope}/module:app/*"]),
        ("${scope}/module:*", ["${scope}/module:*"]),
        ("${scope}/*", ["${scope}/*"]),
        ("*", ["*"]),
        (f"${{scope}}/{NEW}", [f"${{scope}}/{NEW}"]),
        ("${scope}/module:app/naas_abi_marketplace.applications.x/x", None),
        ("${scope}/module:agent/naas_abi_marketplace.applications.x/X", None),
        ("${scope}/module:app/naas_abi_marketplace.applications.git/*", None),
        ("${scope}/nexus:file/*", None),
    ],
)
def test_a_pattern_names_the_new_app_where_it_named_the_old(
    pattern: str, after: list[str] | None
) -> None:
    rewriter = MovedScopes()
    assert rewriter.pattern(pattern) == (after or [pattern])
    # Again: nothing more.
    again = [moved for each in rewriter.pattern(pattern) for moved in rewriter.pattern(each)]
    assert list(dict.fromkeys(again)) == (after or [pattern])
    assert rewriter.notes == []


def test_a_wildcard_over_module_itself_is_named_not_rewritten() -> None:
    rewriter = MovedScopes()
    pattern = "${scope}/*naas_abi_marketplace.applications.x*"
    assert rewriter.pattern(pattern) == [pattern]
    assert rewriter.notes and pattern in rewriter.notes[0]


def test_a_statement_past_the_pattern_limit_is_split() -> None:
    others = [f"${{scope}}/module:app/m{i}/a" for i in range(MAX_PATTERNS - 1)]
    statement = {
        "sid": "Modules",
        "effect": "Allow",
        "actions": ["module:*"],
        "resources": [*others, "${scope}/module:app/naas_abi_marketplace.applications.x/*"],
    }
    rewriter = MovedScopes()
    first, second = rewriter.statements([statement])
    assert first["resources"] == statement["resources"]
    assert second == {**statement, "sid": "Modules2", "resources": [f"${{scope}}/{NEW}"]}
    assert rewriter.statements([first, second]) == [first, second]


# -- in IAM ------------------------------------------------------------------------------

# Each user's policy at ws-1: (effect, resources), on top of what ``module:app/*``
# gives the Deny's holders.
GRANTS = {
    "exact": [("Allow", [f"${{scope}}/{OLD}"])],
    "module_wide": [
        ("Allow", ["${scope}/module:app/naas_abi_marketplace.applications.x/*"]),
    ],
    "every_app": [("Allow", ["${scope}/module:app/*"])],
    "denied_exact": [("Allow", ["${scope}/module:app/*"]), ("Deny", [f"${{scope}}/{OLD}"])],
    "denied_module": [
        ("Allow", ["${scope}/module:app/*"]),
        ("Deny", ["${scope}/module:*/naas_abi_marketplace.applications.x/*"]),
    ],
    "older_id": [("Allow", ["${scope}/module:app/naas_abi_marketplace.applications.x/x"])],
    "nothing": [],
}


def _world(store) -> tuple[NexusIam, str]:
    nexus = NexusIam(store=store, features_with_roles=False)
    ws = nexus.workspace("org-1", "ws-1")
    for user, statements in GRANTS.items():
        nexus.grant(user, "member", ws)
        for effect, resources in statements:
            (nexus.allow if effect == "Allow" else nexus.deny)(user, [OPEN], resources, ws)
    return nexus, ws


def _opens(nexus: NexusIam, ws: str, scope: str) -> dict[str, bool]:
    found = {}
    for user in GRANTS:
        with use_call_context(NexusIam.context(user)):
            found[user] = nexus.iam.authorize(OPEN, f"{ws}/{scope}").allowed
    return found


@pytest.mark.parametrize("store", ["memory", "sqlite"])
def test_who_opened_the_old_app_opens_the_new_one(store, tmp_path) -> None:
    nexus, ws = _world(
        IAMStoreMemory() if store == "memory" else IAMStoreSQLite(str(tmp_path / "iam.sqlite"))
    )
    with as_service_account("engine"):
        alice = nexus.principal("exact")
        nexus.iam.create_key(
            alice,
            description="narrowed to the X app",
            scope=[{"effect": "Allow", "actions": [OPEN], "resources": [f"abi:*/{OLD}"]}],
        )
    before = _opens(nexus, ws, OLD)
    assert before == {
        "exact": True,
        "module_wide": True,
        "every_app": True,
        "denied_exact": False,
        "denied_module": False,
        "older_id": False,
        "nothing": False,
    }

    report = module_moves.rewrite(nexus.iam)

    assert _opens(nexus, ws, NEW) == before
    assert report.counts["policies"] == 4  # exact, module_wide and both Denies
    assert report.counts["keys"] == 1
    assert report.notes == []
    (key,) = nexus.iam.store.list_keys(alice)
    assert key.scope[0]["resources"] == [f"abi:*/{NEW}"]
    # Again: nothing to do.
    assert not any(module_moves.rewrite(nexus.iam).counts.values())


# -- at start, and Nexus's rows ----------------------------------------------------------


@pytest_asyncio.fixture
async def nexus_db(tmp_path, monkeypatch):
    """nexus.db built from every migration, as a start builds it."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")
    monkeypatch.setattr(database, "async_engine", engine)
    monkeypatch.setattr(database, "_is_sqlite", True)
    with contextlib.redirect_stdout(io.StringIO()):
        await database.init_db()
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


async def _migrate_again() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        await database.init_db()


@pytest.mark.asyncio
async def test_the_rows_name_the_new_app_id(nexus_db: AsyncSession) -> None:
    seed = json.dumps({"apps": [OLD_APP_ID, "acme.crm:deals"], "agents": []}, sort_keys=True)
    await nexus_db.execute(text("INSERT INTO users (id, email, name) VALUES ('u', 'u@x.io', 'U')"))
    for ws, catalog_seed in (("ws-a", seed), ("ws-b", None), ("ws-c", '{"apps": []}')):
        await nexus_db.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, owner_id, catalog_seed) "
                "VALUES (:ws, :ws, :ws, 'u', :seed)"
            ),
            {"ws": ws, "seed": catalog_seed},
        )
    for row_id, ws, app_id in (
        ("a1", "ws-a", OLD_APP_ID),
        ("a2", "ws-a", "acme.crm:deals"),
        ("b1", "ws-b", OLD_APP_ID),  # both: the new id's row is kept
        ("b2", "ws-b", NEW_APP_ID),
        ("c1", "ws-c", OLDER_APP_ID),
    ):
        await nexus_db.execute(
            text("INSERT INTO app_configs (id, workspace_id, app_id) VALUES (:id, :ws, :app)"),
            {"id": row_id, "ws": ws, "app": app_id},
        )
    await nexus_db.commit()

    for _ in range(2):  # every start runs the migrations
        await _migrate_again()
        rows = (
            await nexus_db.execute(
                text("SELECT id, workspace_id, app_id FROM app_configs ORDER BY id")
            )
        ).all()
        assert [tuple(r) for r in rows] == [
            ("a1", "ws-a", NEW_APP_ID),
            ("a2", "ws-a", "acme.crm:deals"),
            ("b2", "ws-b", NEW_APP_ID),
            ("c1", "ws-c", OLDER_APP_ID),
        ]
        seeds = dict(
            (await nexus_db.execute(text("SELECT id, catalog_seed FROM workspaces"))).all()
        )
        assert json.loads(seeds["ws-a"]) == {"apps": [NEW_APP_ID, "acme.crm:deals"], "agents": []}
        assert seeds["ws-b"] is None
        assert seeds["ws-c"] == '{"apps": []}'


async def _record(db: AsyncSession, name: str) -> None:
    await db.execute(text("INSERT INTO iam_migrations (name) VALUES (:n)"), {"n": name})
    await db.commit()


@pytest.mark.asyncio
async def test_the_move_runs_once_after_the_names_move(nexus_db: AsyncSession) -> None:
    nexus, ws = _world(IAMStoreMemory())
    with nexus.installed():
        # The names are not container paths yet: it waits.
        assert await module_moves.migrate(nexus_db) is None
        assert _opens(nexus, ws, NEW)["exact"] is False
        await _record(nexus_db, container_names.MIGRATION_NAME)

        report = await module_moves.migrate(nexus_db)

        assert report is not None and report.counts["policies"] == 4
        assert _opens(nexus, ws, NEW)["exact"] is True
        assert await container_names.recorded(nexus_db, module_moves.MIGRATION_NAME)
        assert await module_moves.migrate(nexus_db) is None

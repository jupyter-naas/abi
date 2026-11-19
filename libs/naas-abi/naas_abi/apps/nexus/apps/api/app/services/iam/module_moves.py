"""Module scopes that moved to another module, rewritten in IAM once, at start.

An engine module's item that a remote module now serves has another module
scope (``app/<module>/<name>``, core ``services/iam/module_scopes``): the X
"Recent Tweets" app was ``app/naas_abi_marketplace.applications.x/x_proxy``
(app id ``naas_abi_marketplace.applications.x:x_proxy``) and is
``app/applications.x/x_proxy`` (``remote/applications.x:x_proxy``,
``apps/scopes.app_scope``). A grant naming the old scope reaches nothing any
more, so IAM's stored names follow (``iam.rewrite_names(MovedScopes)``, one
transaction): policy documents (managed ones and manifests too) and keys'
narrowing statements. Nothing else IAM stores names a module scope.

Nobody gains or loses access, in each statement (an Allow or a Deny):

* a pattern naming exactly the old item names the new one instead
  (``${scope}/module:app/naas_abi_marketplace.applications.x/x_proxy`` becomes
  ``${scope}/module:app/applications.x/x_proxy``, whatever names the container);
* a pattern over the old module that reaches the old item but not the new one
  (``.../module:app/naas_abi_marketplace.applications.x/*``,
  ``.../module:*/naas_abi_marketplace.*``) is kept, and the new item is named
  beside it, alone: the new module's other items are not reached;
* a pattern that already reaches the new item (``${scope}/module:app/*``,
  ``${scope}/*``) is left as it is;
* a pattern that reaches the old item through a wildcard over ``module:`` itself
  and not the new one is left, named in the report's notes (no Nexus screen
  writes one).

The rows Nexus keeps of the app id (``app_configs``, a workspace's catalog
seed) are moved by migration ``0072_remote_x_app.sql``. Runs after the names
became container paths (``container_names_v1``, itself after the sets' move,
which still grants from those rows), recorded in ``iam_migrations`` as
``module_moves_v1``; a failure is logged and tried again at the next start. A
later move adds its entry to ``MOVES`` and raises the version: the moves made
before are found done.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import container_names, runtime
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import LegacyPlacement, NameRewriter
from naas_abi_core.services.iam.module_scopes import APP, scope_resource
from naas_abi_core.services.iam.names import PLATFORM, UNRESOLVED, matches
from naas_abi_core.services.iam.policy import MAX_PATTERNS, MAX_STATEMENTS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)

MIGRATION_NAME = "module_moves_v1"
AFTER = (container_names.MIGRATION_NAME,)
# Where a module scope starts in a name: ``<container>/module:<type>/<module>/<name>``.
_MARK = "module:"
# A container to try the patterns with no literal ``module:`` on.
_PROBE = "abi:nexus:workspace/_probe"


@dataclass(frozen=True)
class Move:
    """A module scope now another module's: ``type`` and ``old_module``'s
    ``old_name`` is ``new_module``'s ``new_name``."""

    type: str
    old_module: str
    old_name: str
    new_module: str
    new_name: str

    @property
    def old(self) -> str:
        """``module:<type>/<module>/<name>``, below any container."""
        return scope_resource(self.type, self.old_module, self.old_name).removeprefix(PLATFORM)

    @property
    def new(self) -> str:
        return scope_resource(self.type, self.new_module, self.new_name).removeprefix(PLATFORM)


MOVES: tuple[Move, ...] = (
    # The X "Recent Tweets" app, from the engine module to the remote one (#1423).
    Move(APP, "naas_abi_marketplace.applications.x", "x_proxy", "applications.x", "x_proxy"),
)


class MoveStop(Exception):
    """A document the move cannot rewrite within IAM's limits: nothing is recorded."""


@dataclass
class MovedScopes(NameRewriter):
    """Each ``moves`` item's old scope named as the new one (see the module);
    containers, owners, scopes and placements are left as they are."""

    moves: Sequence[Move] = MOVES
    notes: list[str] = field(default_factory=list)

    def scope(self, scope: str | None) -> str | None:
        return scope

    def owner(self, owner: str) -> str:
        return owner

    def placement(self, placement: LegacyPlacement) -> str:
        # UNRESOLVED: the store keeps the placement as it was.
        return UNRESOLVED

    def pattern(self, pattern: str) -> list[str]:
        """What ``pattern`` becomes: itself, the new name in its place, or itself
        and the new name."""
        found = [pattern]
        for move in self.moves:
            found = [moved for each in found for moved in self._moved(each, move)]
        return found

    def _moved(self, pattern: str, move: Move) -> list[str]:
        head, mark, rest = pattern.rpartition(_MARK)
        if not mark:
            probe = pattern.replace("${scope}", _PROBE)
            if matches(probe, f"{_PROBE}/{move.old}") and not matches(
                probe, f"{_PROBE}/{move.new}"
            ):
                self.notes.append(
                    f"{pattern!r} reaches {move.old} but not {move.new}: left as it is"
                )
            return [pattern]
        old_rest = move.old.removeprefix(_MARK)
        new_rest = move.new.removeprefix(_MARK)
        if not matches(rest, old_rest) or matches(rest, new_rest):
            return [pattern]
        if rest == old_rest:
            return [head + move.new]
        return [pattern, head + move.new]

    def statements(self, statements: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
        # A name added beside a pattern once is not added again, though a split
        # put it in a statement of its own.
        named = {
            (_kind(statement), resource)
            for statement in statements
            if isinstance(statement.get("resources"), list)
            for resource in statement["resources"]
        }
        found: list[Mapping[str, Any]] = []
        for statement in statements:
            resources = statement.get("resources")
            if not isinstance(resources, list):
                found.append(statement)
                continue
            rewritten: list[str] = []
            for each in resources:
                moved = self.pattern(str(each))
                if each in moved:  # kept: what is named beside it, unless named already
                    moved = [m for m in moved if m == each or (_kind(statement), m) not in named]
                rewritten += moved
            rewritten = list(dict.fromkeys(rewritten))
            if rewritten == resources:
                found.append(statement)
                continue
            for part in range(0, len(rewritten), MAX_PATTERNS):
                piece = {**statement, "resources": rewritten[part : part + MAX_PATTERNS]}
                sid = statement.get("sid")
                if part and isinstance(sid, str):
                    piece["sid"] = f"{sid}{part // MAX_PATTERNS + 1}"[:64]
                found.append(piece)
        return found

    def document(self, document: Mapping[str, Any]) -> Mapping[str, Any]:
        statements = document.get("statements")
        if not isinstance(statements, list):
            return document
        rewritten = list(self.statements(statements))
        if rewritten == statements:
            return document
        if len(rewritten) > MAX_STATEMENTS:
            raise MoveStop(
                f"a policy would need {len(rewritten)} statements (more than {MAX_STATEMENTS})"
            )
        return {**document, "statements": rewritten}


def _kind(statement: Mapping[str, Any]) -> tuple[Any, ...]:
    """What a statement does, but where: its effect and its actions."""
    actions = statement.get("actions")
    return (statement.get("effect"), tuple(actions) if isinstance(actions, list) else actions)


@dataclass
class Report:
    counts: dict[str, int]
    notes: list[str]


def rewrite(iam: Any, moves: Sequence[Move] = MOVES) -> Report:
    """Rewrite every stored name of ``moves``' old scopes, as the engine."""
    with as_service_account("engine"):
        rewriter = MovedScopes(list(moves))
        counts = iam.rewrite_names(rewriter)
    return Report(counts, list(dict.fromkeys(rewriter.notes)))


async def migrate(db: AsyncSession) -> Report | None:
    """Move the old scopes of ``MOVES`` in IAM, once (see the module). None when it
    did not run: done already, waiting for the names' move, or failed (logged,
    tried again at the next start)."""
    if await container_names.recorded(db, MIGRATION_NAME):
        return None
    for before in AFTER:
        if not await container_names.recorded(db, before):
            _log.warning("The moved module scopes wait for %s", before)
            return None
    try:
        report = await run_in_threadpool(rewrite, runtime.iam())
    except Exception:  # noqa: BLE001 - nothing recorded: tried again at the next start
        _log.exception("The module scopes that moved to another module were not rewritten")
        return None
    await db.execute(
        text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
        {
            "n": MIGRATION_NAME,
            "at": datetime.now(UTC).replace(tzinfo=None),
            "r": json.dumps({"counts": report.counts, "notes": report.notes}),
        },
    )
    await db.commit()
    for note in report.notes:
        _log.warning("Moved module scopes: %s", note)
    return report

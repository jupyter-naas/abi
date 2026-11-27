"""The workspaces' graph assignments move into their offers, once (``graphs_offer_v1``;
ADR ``20261125_offer_gives_outside_resources``, decision 5).

An earlier version enforced a workspace's graph assignments (``workspace_resource_policies``,
else its configuration) through two platform policies per workspace,
``workspace.<ws>.graphs.read`` (the graphs it reads or writes, Denies of what it closes)
and ``workspace.<ws>.graphs.write`` (``Insert``, ``Remove``), attached unscoped to each of
its people and kept in step with its memberships by Nexus (``graph_grants``). A policy
past ``policy.MAX_PATTERNS`` names could not be written: those workspaces were given
nothing. The offer says it now: the Graphs part of "<W> access" (``given_graphs``), which
IAM gives W's people while they belong to W, each within their level.

For each workspace Nexus records, its effective assignment (the saved row, else the
configuration's, as ``load_resource_policy`` reads it) becomes its graph sections; the
graphs are named wherever IAM places them (``given_graphs.anywhere_names``), as the
policies named them. Then the two policies of each moved workspace (and of a workspace
Nexus no longer records) are detached from everyone and deleted. A workspace with
something to move and no access policy yet waits for a start where it has one. Recorded
in ``iam_migrations`` once nothing failed or waits. As ``api``.

A workspace's configuration made later (a seed's) is written into its offer when its
access policy is made (``configured_graphs``, ``container_defaults.migrate``).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import unquote

from naas_abi.apps.nexus.apps.api.app.services.iam import given_graphs, offer_moves
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    PLATFORM,
    is_workspace_container,
    org_of,
    workspace_container,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    GRAPH_FIELDS,
    Offer,
    offer_of,
    with_offer,
)
from naas_abi.apps.nexus.graph_policy_config import (
    SCHEMA_GRAPH,
    WorkspaceGraphPolicyConfig,
    is_nexus_system_graph,
    without_system_graphs,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError
from naas_abi_core.services.iam.policy import MAX_PATTERNS
from naas_abi_core.services.triple_store.iam_catalog import SERVICE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

MIGRATION_NAME = "graphs_offer_v1"

# What the earlier version wrote (``graph_grants``).
READ = "read"
WRITE = "write"
_POLICY_NAME = re.compile(r"^workspace\.(?P<workspace>.+)\.graphs\.(?P<kind>read|write)$")
DEFAULT = WorkspaceGraphPolicyConfig()


def policy_name(workspace: str, kind: str) -> str:
    """The name of one of the two policies an earlier version wrote for a workspace."""
    return f"workspace.{workspace}.graphs.{kind}"


@dataclass(frozen=True)
class Move:
    """One workspace: its container, its "<W> access", its effective assignment and the
    graphs the application graph records as its own (not yet placed by IAM)."""

    workspace: str
    container: str | None
    policy_id: str | None
    config: WorkspaceGraphPolicyConfig
    legacy_owned: frozenset[str] = frozenset()


@dataclass
class Report:
    # Workspaces whose "<W> access" now says their assignment.
    written: list[str] = field(default_factory=list)
    # Workspaces whose offer said it already.
    kept: list[str] = field(default_factory=list)
    # Workspaces with something to move and no access policy yet (the next start).
    waiting: list[str] = field(default_factory=list)
    policies_deleted: int = 0
    attachments_deleted: int = 0
    # Workspaces given their graphs for the first time: a policy of theirs passed
    # ``MAX_PATTERNS`` names and was never written.
    widened: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "written": sorted(self.written),
            "kept": len(self.kept),
            "waiting": sorted(self.waiting),
            "policies_deleted": self.policies_deleted,
            "attachments_deleted": self.attachments_deleted,
            "widened": sorted(self.widened),
            "failed": dict(sorted(self.failed.items())),
        }


def _pages(listing: Any, **kwargs: Any) -> list[Any]:
    found: list[Any] = []
    after: str | None = None
    while True:
        page = listing(limit=500, after=after, **kwargs)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def legacy_policies(iam: Any) -> dict[str, dict[str, str]]:
    """``{workspace: {kind: policy id}}`` of the policies an earlier version wrote: at
    the platform (one of that name owned by an organization or a workspace is someone
    else's)."""
    found: dict[str, dict[str, str]] = {}
    for policy in _pages(iam.list_policies):
        named = _POLICY_NAME.match(str(policy.name))
        if named is None or str(getattr(policy, "owner_scope", PLATFORM)) != PLATFORM:
            continue
        found.setdefault(named.group("workspace"), {})[named.group("kind")] = str(policy.id)
    return found


def _placed(iam: Any) -> dict[str, str]:
    """``{graph: container}`` of every graph IAM placed."""
    return {
        unquote(p.id_key): str(p.container)
        for p in iam.list_placements(SERVICE)
        if not p.id_key.endswith("*")
    }


def _owned(placed: Mapping[str, str], workspace: str) -> set[str]:
    return {iri for iri, container in placed.items() if workspace_of(container) == workspace}


def _reached(catalog: Iterable[str], placed: Mapping[str, str], container: str) -> set[str]:
    """What ``read_all`` reached when the earlier version wrote it (``graph_iam.within``):
    the graphs of the workspace's organization (its own for a workspace in none), and the
    schema graph."""
    org = org_of(container)
    found = set()
    for iri in catalog:
        where = placed.get(iri)
        if iri == SCHEMA_GRAPH and where in (None, PLATFORM):
            found.add(iri)
        elif where and not is_nexus_system_graph(iri):
            if where == container or (org is not None and org_of(where) == org):
                found.add(iri)
    return found


def _was_never_written(
    move: Move, legacy: Mapping[str, str], owned: set[str], catalog: Iterable[str], placed: Any
) -> bool:
    """Whether a policy of the earlier version, which ``move``'s assignment needed, passed
    ``MAX_PATTERNS`` names (each graph twice) and is missing."""
    config = move.config
    shared = without_system_graphs(set(config.read) | set(config.write))
    if config.read_all and move.container:
        shared |= _reached(catalog, placed, move.container) | set(move.legacy_owned)
    shared = without_system_graphs(shared)
    closed = owned - shared if not config.include_owned else set()
    written = without_system_graphs(set(config.write))
    return (READ not in legacy and max(2 * len(shared), len(closed)) > MAX_PATTERNS) or (
        WRITE not in legacy and 2 * len(written) > MAX_PATTERNS
    )


def apply(iam: Any, moves: Sequence[Move], *, catalog: Iterable[str] = ()) -> Report:
    """Write each workspace's assignment into its "<W> access", then delete the policies of
    the earlier version (those of a waiting or failed workspace are kept). ``catalog``:
    the graphs that exist, to name the workspaces whose ``read_all`` passed the pattern
    limit. As ``api``. Idempotent: a second pass writes nothing and deletes nothing."""
    report = Report()
    catalog = set(catalog)
    with as_service_account("api"):
        legacy = legacy_policies(iam)
        placed = _placed(iam)
        held_back: set[str] = set()
        for move in moves:
            has_legacy = move.workspace in legacy
            try:
                if move.policy_id is None or move.container is None:
                    if move.config != DEFAULT or has_legacy:
                        report.waiting.append(move.workspace)
                        held_back.add(move.workspace)
                    continue
                owned = _owned(placed, move.workspace) | set(move.legacy_owned)
                policy = iam.get_policy(move.policy_id)
                held = offer_of(policy.document)
                fields = given_graphs.fields_of(
                    move.config,
                    container=move.container,
                    owned=owned,
                    name_of=given_graphs.anywhere_names,
                    current={f: getattr(held, f) for f in GRAPH_FIELDS},
                )
                wanted = replace(held, **fields)
                if wanted != held:
                    iam.update_policy(
                        policy.id,
                        expected_revision=policy.revision,
                        document=with_offer(policy.document, wanted),
                    )
                    report.written.append(move.workspace)
                elif move.config != DEFAULT:
                    report.kept.append(move.workspace)
                if move.config != DEFAULT and _was_never_written(
                    move, legacy.get(move.workspace, {}), owned, catalog, placed
                ):
                    report.widened.append(move.workspace)
            except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
                report.failed[move.workspace] = str(exc)
                held_back.add(move.workspace)
        for workspace, kinds in sorted(legacy.items()):
            if workspace in held_back:
                continue
            for kind, policy_id in sorted(kinds.items()):
                try:
                    for attachment in iam.list_attachments(policy_id=policy_id):
                        iam.detach_policy(policy_id, attachment.principal_id, attachment.scope)
                        report.attachments_deleted += 1
                    iam.delete_policy(policy_id)
                    report.policies_deleted += 1
                except IAMNotFoundError:
                    continue
                except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
                    report.failed[policy_name(workspace, kind)] = str(exc)
    return report


# -- what Nexus records -------------------------------------------------------------------


def _catalog_store() -> Any:
    """The application's triple store, for the graphs the application graph records;
    None when there is none (a test, no engine)."""
    try:
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_placements import (  # noqa: E501
            _store,
        )

        return _store()
    except Exception:  # noqa: BLE001 - no store: the graphs IAM placed are the ones
        logger.warning("Graphs into the offer: no triple store, only IAM's placements read")
        return None


async def _config(db: AsyncSession, workspace_id: str) -> WorkspaceGraphPolicyConfig:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.resource_access_postgres import (  # noqa: E501
        load_resource_policy,
    )

    saved = await load_resource_policy(db, workspace_id, "graphs")
    return WorkspaceGraphPolicyConfig.model_validate(saved.data)


def _legacy_owned(store: Any, workspace_id: str) -> frozenset[str]:
    if store is None:
        return frozenset()
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_placements import (  # noqa: E501
        legacy_owned_graphs,
    )

    return frozenset(legacy_owned_graphs(store, workspace_id))


async def moves_of(db: AsyncSession, *, store: Any = None) -> tuple[list[Move], dict[str, str]]:
    """Each workspace Nexus records, with its access policy and its effective assignment;
    and the workspaces whose assignment could not be read (``{workspace: why}``)."""
    policies = await offer_moves.access_policies(db)
    containers = {
        workspace: (container, policy_id)
        for container, policy_id in policies.items()
        if is_workspace_container(container) and (workspace := workspace_of(container))
    }
    rows = (await db.execute(text("SELECT id FROM workspaces ORDER BY id"))).all()
    moves: list[Move] = []
    failed: dict[str, str] = {}
    for (workspace_id,) in rows:
        workspace = str(workspace_id)
        try:
            config = await _config(db, workspace)
            legacy_owned = await run_in_threadpool(_legacy_owned, store, workspace)
        except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
            failed[workspace] = str(exc)
            continue
        container, policy_id = containers.get(workspace, (None, None))
        moves.append(Move(workspace, container, policy_id, config, legacy_owned))
    return moves, failed


async def migrate(db: AsyncSession, iam: Any, *, store: Any = None) -> Report | None:
    """Once: the workspaces' graph assignments into their offers. None when recorded."""
    if await offer_moves.recorded(db, MIGRATION_NAME):
        return None
    store = store if store is not None else _catalog_store()
    moves, unread = await moves_of(db, store=store)
    catalog: set[str] = set()
    if store is not None and any(m.config.read_all for m in moves):
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (  # noqa: E501
            catalog_graphs,
        )

        catalog = await run_in_threadpool(catalog_graphs, store)
    report = await run_in_threadpool(lambda: apply(iam, moves, catalog=catalog))
    report.failed.update(unread)
    if report.written:
        from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

        AUTHZ.forget_offers()
    if report.failed or report.waiting:
        logger.warning(
            "Graphs into the offer: not recorded yet (next start): failed %s, waiting %s",
            report.failed,
            report.waiting,
        )
        return report
    await offer_moves.record(db, MIGRATION_NAME, report.to_dict())
    if report.widened:
        logger.warning(
            "Graphs into the offer: given their graphs for the first time (a policy of "
            "theirs passed %d names): %s",
            MAX_PATTERNS,
            report.widened,
        )
    logger.info("Graphs in the offer: %s", report.to_dict())
    return report


# -- a seeded workspace made later ----------------------------------------------------------


async def configured_graphs(
    db: AsyncSession, workspaces: Mapping[str, str | None]
) -> dict[str, Offer]:
    """``{workspace id: Offer}`` of the Graphs part each workspace's effective assignment
    says (``{workspace id: organization id}``; its configuration's, for a seeded one with
    no saved row): what its access policy is made with. A workspace that says nothing
    (the defaults) is left out."""
    found: dict[str, Offer] = {}
    for workspace_id, org_id in sorted(workspaces.items()):
        try:
            config = await _config(db, workspace_id)
        except Exception:  # noqa: BLE001 - made without; an administrator gives them
            logger.exception(f"The graph assignment of {workspace_id} could not be read")
            continue
        if config == DEFAULT:
            continue
        container = workspace_container(org_id, workspace_id)
        found[workspace_id] = Offer(**given_graphs.fields_of(config, container=container))
    return found


__all__ = [
    "MIGRATION_NAME",
    "READ",
    "WRITE",
    "Move",
    "Report",
    "apply",
    "configured_graphs",
    "legacy_policies",
    "migrate",
    "moves_of",
    "policy_name",
]

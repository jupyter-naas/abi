"""A workspace's graph assignments as IAM policies.

``workspace_resource_policies`` stays the document administrators edit (what
a workspace reads, writes, may create); IAM enforces it. A workspace's own
graphs need no statement: IAM placed them in it, so its members' roles reach
them (``graph_placements``). What a workspace *shares* or is *given* does:

* ``workspace.<ws>.graphs.read``: Allow the list and read actions of the graphs
  the workspace reads or writes, and Deny what the workspace closes (creating
  graphs, its own graphs when it excludes them). Held by every member.
* ``workspace.<ws>.graphs.write``: Allow ``Insert`` and ``Remove`` on the
  graphs it may write. Held by members, admins and owners, never by viewers.

A grant onto another workspace's graph cannot be attached at the workspace's
scope (a scoped attachment keeps only ``${scope}:`` resources), so each holder
is attached the policy itself, without scope: the policy is named for the
workspace and held only while the user holds a role there. ``sync_members``
keeps the holders in step with the workspace's memberships.

Sharing never gives lifecycle control: ``ClearGraph`` and ``DropGraph`` stay
with the workspace that owns the graph.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import graph_iam
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
    catalog_graphs,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import NO_ORG, workspace_scope
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_GRAPH,
    WorkspaceGraphPolicyConfig,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError
from naas_abi_core.services.iam.names import encode_id
from naas_abi_core.services.iam.policy import POLICY_VERSION, PolicyDocument
from naas_abi_core.services.triple_store.iam_catalog import CATALOG, GRAPH, SERVICE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

READ = "read"
WRITE = "write"
# Roles that may write what the workspace shares for writing (a viewer never does).
WRITER_ROLES = frozenset({"owner", "admin", "member"})


def _actions(*levels: str, creates: bool = False) -> list[str]:
    return [
        CATALOG.qualified(a.name)
        for a in CATALOG.actions
        if GRAPH in a.resource_types and a.level in levels and a.creates == creates
    ]


READ_ACTIONS = _actions("list", "read")
WRITE_ACTIONS = _actions("write")
CREATE_ACTIONS = _actions("write", creates=True)
ALL_ACTIONS = _actions("list", "read", "write", "admin") + CREATE_ACTIONS


def policy_name(workspace: str, kind: str) -> str:
    return f"workspace.{workspace}.graphs.{kind}"


def _anywhere(iri: str) -> str:
    """The graph wherever IAM placed it: an assignment names the graph, and the
    graph keeps its identity if it moves."""
    return f"abi:*:*:{SERVICE}:{GRAPH}/{encode_id(iri, 'opaque')}"


def _in(org: str, workspace: str, iri: str = "*") -> str:
    target = "*" if iri == "*" else encode_id(iri, "opaque")
    return f"abi:{org}:{workspace}:{SERVICE}:{GRAPH}/{target}"


@dataclass(frozen=True)
class Assignment:
    """What the policies of one workspace say, as IAM documents (None: nothing)."""

    read: dict[str, Any] | None
    write: dict[str, Any] | None


def assignment_of(
    config: WorkspaceGraphPolicyConfig,
    *,
    org: str,
    workspace: str,
    owned: Iterable[str] = (),
    catalog: Iterable[str] = (),
) -> Assignment:
    """The statements of ``config`` for ``workspace``.

    ``catalog`` is read when ``read_all`` is set; it is the graphs that exist
    when the assignment is applied, so a graph created later is shared at the
    next sync. ``owned`` is what the workspace owns, for the ones it excludes.
    """
    shared = set(config.read) | set(config.write)
    if config.read_all:
        shared |= set(catalog)
    shared.discard(NEXUS_GRAPH)  # the application catalog is never shared
    reading: list[dict[str, Any]] = []
    if shared:
        reading.append(
            {
                "sid": "SharedGraphsRead",
                "effect": "Allow",
                "actions": READ_ACTIONS,
                "resources": [_anywhere(iri) for iri in sorted(shared)],
            }
        )
    if not (config.allow_create and config.include_owned):
        reading.append(
            {
                "sid": "NoNewGraphs",
                "effect": "Deny",
                "actions": CREATE_ACTIONS,
                "resources": [_in(org, workspace)],
            }
        )
    if not config.include_owned:
        closed = sorted(set(owned) - shared)
        if closed:
            reading.append(
                {
                    "sid": "OwnGraphsClosed",
                    "effect": "Deny",
                    "actions": ALL_ACTIONS,
                    "resources": [_in(org, workspace, iri) for iri in closed],
                }
            )
    writing: list[dict[str, Any]] = []
    if config.write:
        writing.append(
            {
                "sid": "SharedGraphsWrite",
                "effect": "Allow",
                "actions": WRITE_ACTIONS,
                "resources": [_anywhere(iri) for iri in sorted(config.write)],
            }
        )

    def document(statements: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not statements:
            return None
        return {"version": POLICY_VERSION, "statements": statements}

    return Assignment(document(reading), document(writing))


class GraphGrants:
    """Writes the assignments of workspaces into IAM, as ``api``."""

    def __init__(self) -> None:
        self._ids: dict[str, str] = {}
        # One scan of the policy names, kept for ``_INDEX_SECONDS``: a name it did
        # not see is missing, without asking IAM again (boot asks for every
        # workspace and kind).
        self._scanned_at: float | None = None

    # -- policies, found by name ---------------------------------------------------

    def _scan(self, iam: Any) -> None:
        names: dict[str, str] = {}
        after: str | None = None
        while True:
            page = iam.list_policies(limit=200, after=after)
            names.update({p.name: str(p.id) for p in page.items if p.name.startswith("workspace.")})
            if page.next_after is None:
                break
            after = page.next_after
        self._ids = names
        self._scanned_at = time.monotonic()

    def _find(self, iam: Any, name: str) -> str | None:
        if self._scanned_at is None or time.monotonic() - self._scanned_at > _INDEX_SECONDS:
            self._scan(iam)
        known = self._ids.get(name)
        if known is None:
            return None
        try:
            if iam.get_policy(known).name == name:
                return known
        except IAMNotFoundError:
            pass
        # Gone since the scan (another process): scan again, once.
        self._scan(iam)
        return self._ids.get(name)

    def _apply(
        self,
        iam: Any,
        workspace: str,
        kind: str,
        document: dict[str, Any] | None,
        holders: set[str],
    ) -> None:
        name = policy_name(workspace, kind)
        policy_id = self._find(iam, name)
        if document is None:
            if policy_id is not None:
                for attachment in iam.list_attachments(policy_id=policy_id):
                    iam.detach_policy(policy_id, attachment.principal_id, attachment.scope)
                iam.delete_policy(policy_id)
                self._ids.pop(name, None)
            return
        wanted = PolicyDocument.from_dict(document)
        if policy_id is None:
            policy = iam.create_policy(
                name, wanted, description=f"Graphs of workspace {workspace} ({kind})"
            )
            policy_id = str(policy.id)
            self._ids[name] = policy_id
        else:
            current = iam.get_policy(policy_id)
            if current.document.to_dict() != wanted.to_dict():
                iam.update_policy(policy_id, expected_revision=current.revision, document=wanted)
        held = {
            a.principal_id for a in iam.list_attachments(policy_id=policy_id) if a.scope is None
        }
        for principal_id in sorted(holders - held):
            iam.attach_policy(policy_id, principal_id)
        for principal_id in sorted(held - holders):
            iam.detach_policy(policy_id, principal_id)

    # -- what a workspace holds ----------------------------------------------------

    async def _holders(self, org: str, workspace: str) -> tuple[set[str], set[str]]:
        members = await MEMBERSHIPS.members(workspace_scope(org, workspace))
        readers = {m.principal_id for m in members}
        writers = {m.principal_id for m in members if m.role in WRITER_ROLES}
        return readers, writers

    async def apply(
        self,
        workspace_id: str,
        config: WorkspaceGraphPolicyConfig,
        *,
        store: Any = None,
        legacy_owned: Iterable[str] = (),
    ) -> None:
        """Make IAM say what ``config`` says for the workspace, and hold it for
        its current members."""
        org = await AUTHZ.org_of(workspace_id) or NO_ORG
        readers, writers = await self._holders(org, workspace_id)

        recorded = await self._recorded_owners(store) if config.read_all and store else {}

        def work() -> None:
            iam = runtime.iam()
            owned = graph_iam.owned_by(workspace_id) | set(legacy_owned)
            catalog: Iterable[str] = ()
            if config.read_all and store is not None:
                # What exists in the workspace's own organization, never what other
                # tenants keep (the workspace's legacy-recorded graphs are its own).
                catalog = graph_iam.within(
                    catalog_graphs(store) | set(legacy_owned),
                    org=org,
                    workspace=workspace_id,
                    recorded=recorded,
                ) | set(legacy_owned)
            assignment = assignment_of(
                config, org=org, workspace=workspace_id, owned=owned, catalog=catalog
            )
            with as_service_account("api"):
                self._apply(iam, workspace_id, READ, assignment.read, readers)
                self._apply(iam, workspace_id, WRITE, assignment.write, writers)

        await run_in_threadpool(work)

    @staticmethod
    async def _recorded_owners(store: Any) -> dict[str, tuple[str, str]]:
        """``{graph: (org, workspace)}`` of what the application graph records as a
        workspace's: still its workspace's when IAM has not placed it yet."""
        from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_placements import (  # noqa: E501
            legacy_owners,
        )

        found: dict[str, tuple[str, str]] = {}
        orgs: dict[str, str] = {}
        for iri, workspaces in (await run_in_threadpool(legacy_owners, store)).items():
            owner = sorted(workspaces)[0]
            if owner not in orgs:
                orgs[owner] = await AUTHZ.org_of(owner) or NO_ORG
            found[iri] = (orgs[owner], owner)
        return found

    async def sync_members(self, workspace_id: str) -> None:
        """Hold the workspace's policies for exactly its current members: call it
        after any change of who holds a role there."""
        org = await AUTHZ.org_of(workspace_id) or NO_ORG
        readers, writers = await self._holders(org, workspace_id)

        def work() -> None:
            iam = runtime.iam()
            with as_service_account("api"):
                for kind, holders in ((READ, readers), (WRITE, writers)):
                    policy_id = self._find(iam, policy_name(workspace_id, kind))
                    if policy_id is None:
                        continue
                    held = {
                        a.principal_id
                        for a in iam.list_attachments(policy_id=policy_id)
                        if a.scope is None
                    }
                    for principal_id in sorted(holders - held):
                        iam.attach_policy(policy_id, principal_id)
                    for principal_id in sorted(held - holders):
                        iam.detach_policy(policy_id, principal_id)

        await run_in_threadpool(work)

    async def forget(self, workspace_id: str) -> None:
        """A deleted workspace shares and is given nothing."""

        def work() -> None:
            iam = runtime.iam()
            with as_service_account("api"):
                for kind in (READ, WRITE):
                    self._apply(iam, workspace_id, kind, None, set())

        await run_in_threadpool(work)


_INDEX_SECONDS = 60.0

GRANTS = GraphGrants()


@MEMBERSHIPS.on_workspace_roles_changed
async def _follow_roles(workspace_id: str, dropped: bool) -> None:
    """The shared graphs of a workspace follow who belongs to it."""
    if dropped:
        await GRANTS.forget(workspace_id)
    else:
        await GRANTS.sync_members(workspace_id)


async def sync_workspace(db: AsyncSession, workspace_id: str, *, store: Any = None) -> None:
    """Project the saved assignments of one workspace into IAM."""
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_placements import (  # noqa: E501
        legacy_owned_graphs,
    )
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.resource_access_postgres import (  # noqa: E501
        load_resource_policy,
    )

    saved = await load_resource_policy(db, workspace_id, "graphs")
    config = WorkspaceGraphPolicyConfig.model_validate(saved.data)
    legacy = legacy_owned_graphs(store, workspace_id) if store is not None else set()
    await GRANTS.apply(workspace_id, config, store=store, legacy_owned=legacy)


async def sync_all(db: AsyncSession, *, store: Any = None) -> int:
    """Project every workspace's saved assignments into IAM (startup)."""
    ids = [str(row[0]) for row in (await db.execute(text("SELECT id FROM workspaces"))).all()]
    done = 0
    for workspace_id in ids:
        try:
            await sync_workspace(db, workspace_id, store=store)
            done += 1
        except Exception:  # noqa: BLE001 - one workspace never blocks the others
            logger.exception(f"Graph assignments of workspace {workspace_id} not applied")
    return done

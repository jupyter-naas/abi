"""Resolve the ids in event payloads to people, workspaces and roles.

Events store ids only. For a page of events, the distinct ids are resolved in
a handful of SPARQL queries against graph/nexus-identity:
``user_id → nexus:User → nexus:isUserAccountOf → abi:Person``, workspace and
organization profiles, and the access role a user holds in a workspace.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.identity_graph import iris
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.service import IDENTITY_GRAPH_URI
from naas_abi_core import logger
from naas_abi_core.services.event.local_identity import EMAIL_ACTOR_PREFIX

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:@+\-]{1,200}$")
_PREFIXES = (
    "PREFIX nexus: <http://ontology.naas.ai/nexus/>\n"
    "PREFIX abi: <http://ontology.naas.ai/abi/>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
)


@dataclass
class ResolvedUser:
    user_id: str
    name: str | None
    email: str | None
    avatar_url: str | None
    person_iri: str
    account_iri: str
    is_superadmin: bool = False


@dataclass
class ResolvedWorkspace:
    workspace_id: str
    name: str | None
    slug: str | None
    primary_color: str | None
    logo_url: str | None
    iri: str
    organization_name: str | None = None


@dataclass
class ResolvedOrganization:
    organization_id: str
    name: str | None
    slug: str | None
    iri: str


@dataclass
class Identities:
    users: dict[str, ResolvedUser] = field(default_factory=dict)
    workspaces: dict[str, ResolvedWorkspace] = field(default_factory=dict)
    organizations: dict[str, ResolvedOrganization] = field(default_factory=dict)
    # (workspace id, user id) -> owner/admin/member/viewer
    workspace_roles: dict[tuple[str, str], str] = field(default_factory=dict)


def _safe(ids: Iterable[str | None]) -> list[str]:
    return sorted({i for i in ids if i and _SAFE_ID.match(i)})


def _literals(ids: list[str]) -> str:
    return " ".join(f'"{i}"' for i in ids)


def _text(row: Any, name: str) -> str | None:
    value = getattr(row, name, None)
    return str(value) if value is not None else None


class IdentityResolver:
    def __init__(self, query: Callable[[str], Iterable[Any]]):
        self._query = query

    def _run(self, body: str) -> Iterable[Any]:
        return self._query(
            f"{_PREFIXES}SELECT * WHERE {{ GRAPH <{IDENTITY_GRAPH_URI}> {{ {body} }} }}"
        )

    def resolve(
        self,
        user_ids: Iterable[str | None] = (),
        workspace_ids: Iterable[str | None] = (),
        organization_ids: Iterable[str | None] = (),
        memberships: Iterable[tuple[str | None, str | None]] = (),
    ) -> Identities:
        out = Identities()
        safe_users = _safe(user_ids)
        # Terminal events name their actor by git email hash, not by user id.
        hashes = {
            u[len(EMAIL_ACTOR_PREFIX) :]: u for u in safe_users if u.startswith(EMAIL_ACTOR_PREFIX)
        }
        users = [u for u in safe_users if not u.startswith(EMAIL_ACTOR_PREFIX)]
        person_details = """?account nexus:user_id ?uid ; nexus:isUserAccountOf ?person .
                OPTIONAL {{ ?person abi:full_name ?name }}
                OPTIONAL {{ ?account nexus:user_email ?email }}
                OPTIONAL {{ ?account nexus:avatar_url ?avatar }}
                OPTIONAL {{ ?role a nexus:PlatformSuperadminRole ; abi:inheresIn ?person }}"""
        lookups = []
        if users:
            lookups.append(
                (
                    f"VALUES ?key {{ {_literals(users)} }} ?account nexus:user_id ?key .",
                    {u: u for u in users},
                )
            )
        if hashes:
            lookups.append(
                (
                    f"VALUES ?key {{ {_literals(sorted(hashes))} }} ?account nexus:user_email_sha256 ?key .",
                    hashes,
                )
            )
        for match, keys in lookups:
            for row in self._run(f"{match}\n{person_details.format()}"):
                out.users[keys[str(row.key)]] = ResolvedUser(
                    user_id=str(row.uid),
                    name=_text(row, "name"),
                    email=_text(row, "email"),
                    avatar_url=_text(row, "avatar"),
                    person_iri=str(row.person),
                    account_iri=str(row.account),
                    is_superadmin=getattr(row, "role", None) is not None,
                )
        workspaces = _safe(workspace_ids)
        if workspaces:
            for row in self._run(
                f"""VALUES ?id {{ {_literals(workspaces)} }}
                ?ws nexus:workspace_id ?id .
                OPTIONAL {{ ?ws nexus:workspace_name ?name }}
                OPTIONAL {{ ?ws nexus:slug ?slug }}
                OPTIONAL {{ ?ws nexus:primary_color ?color }}
                OPTIONAL {{ ?ws nexus:logo_url ?logo }}
                OPTIONAL {{ ?ws nexus:isWorkspaceOf ?org . ?org rdfs:label ?org_name }}"""
            ):
                workspace_id = str(row.id)
                out.workspaces[workspace_id] = ResolvedWorkspace(
                    workspace_id=workspace_id,
                    name=_text(row, "name"),
                    slug=_text(row, "slug"),
                    primary_color=_text(row, "color"),
                    logo_url=_text(row, "logo"),
                    iri=str(row.ws),
                    organization_name=_text(row, "org_name"),
                )
        organizations = _safe(organization_ids)
        if organizations:
            for row in self._run(
                f"""VALUES ?id {{ {_literals(organizations)} }}
                ?profile nexus:organization_id ?id ; nexus:isOrganizationProfileOf ?org .
                OPTIONAL {{ ?profile nexus:organization_name ?name }}
                OPTIONAL {{ ?profile nexus:slug ?slug }}"""
            ):
                organization_id = str(row.id)
                out.organizations[organization_id] = ResolvedOrganization(
                    organization_id=organization_id,
                    name=_text(row, "name"),
                    slug=_text(row, "slug"),
                    iri=str(row.org),
                )

        # Memberships are keyed by the account's user id; a terminal actor's
        # hash is swapped for the id it resolved to.
        def account_id(user: str) -> str:
            resolved = out.users.get(user)
            return resolved.user_id if resolved is not None else user

        pairs = sorted(
            {
                (w, account_id(u))
                for w, u in memberships
                if w and u and _SAFE_ID.match(w) and _SAFE_ID.match(u)
            }
        )
        if pairs:
            by_iri = {str(iris.workspace_membership_iri(w, u)): (w, u) for w, u in pairs}
            values = " ".join(f"<{iri}>" for iri in by_iri)
            for row in self._run(f"VALUES ?m {{ {values} }} ?m nexus:membership_role ?role ."):
                out.workspace_roles[by_iri[str(row.m)]] = str(row.role)
        return out


def _actor_id(event: dict[str, Any]) -> str | None:
    return event.get("actor_user_id") or event.get("user_id")


def _workspace_id(event: dict[str, Any]) -> str | None:
    return (
        event.get("target_workspace_id")
        or event.get("actor_workspace_id")
        or event.get("workspace_id")
    )


def enrich_events(events: list[dict[str, Any]], resolver: IdentityResolver) -> None:
    """Attach ``_identity`` (names, roles) to each event that references anyone."""
    user_ids = {_actor_id(e) for e in events} | {e.get("target_user_id") for e in events}
    workspace_ids = {_workspace_id(e) for e in events}
    organization_ids = {e.get("target_organization_id") for e in events}
    memberships = {(_workspace_id(e), _actor_id(e)) for e in events} | {
        (_workspace_id(e), e.get("target_user_id")) for e in events
    }
    try:
        identities = resolver.resolve(user_ids, workspace_ids, organization_ids, memberships)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[identity-graph] could not resolve event identities: {exc}")
        return

    for event in events:
        workspace_id = _workspace_id(event)
        identity: dict[str, Any] = {}
        for slot, user_id in (
            ("actor", _actor_id(event)),
            ("subject", event.get("target_user_id")),
        ):
            user = identities.users.get(user_id or "")
            if user is not None:
                identity[slot] = {
                    **asdict(user),
                    "workspace_role": identities.workspace_roles.get(
                        (workspace_id or "", user.user_id)
                    ),
                }
        workspace = identities.workspaces.get(workspace_id or "")
        if workspace is not None:
            identity["workspace"] = asdict(workspace)
        organization = identities.organizations.get(event.get("target_organization_id") or "")
        if organization is not None:
            identity["organization"] = asdict(organization)
        if identity:
            event["_identity"] = identity


class CachedEventEnricher:
    """Enrich single live events, reusing recent resolutions.

    The live admin stream sees every published event; most carry no ids and
    are skipped without a query. The rest share a few actors and workspaces,
    so a resolution is kept for ``ttl_seconds``.
    """

    def __init__(
        self,
        resolver: IdentityResolver,
        ttl_seconds: float = 60.0,
        clock: Callable[[], float] | None = None,
        max_entries: int = 512,
    ):
        import time

        self._resolver = resolver
        self._ttl = ttl_seconds
        self._clock = clock or time.monotonic
        self._max = max_entries
        self._cache: dict[tuple[str | None, ...], tuple[float, dict[str, Any] | None]] = {}

    def enrich(self, event: dict[str, Any]) -> None:
        key = (
            _actor_id(event),
            event.get("target_user_id"),
            _workspace_id(event),
            event.get("target_organization_id"),
        )
        if not any(key):
            return
        now = self._clock()
        hit = self._cache.get(key)
        if hit is not None and now - hit[0] < self._ttl:
            if hit[1] is not None:
                event["_identity"] = {slot: dict(value) for slot, value in hit[1].items()}
            return
        enrich_events([event], self._resolver)
        if len(self._cache) >= self._max:
            self._cache.clear()
        identity = event.get("_identity")
        self._cache[key] = (
            now,
            {slot: dict(v) for slot, v in identity.items()} if identity else None,
        )

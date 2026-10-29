"""What the graph domain asks IAM, beyond the checks the kernel makes itself.

The kernel's triple store authorizes every call for the signed-in user, by where
IAM placed each graph (``triple_store:graph/<iri>``). Nexus asks IAM only what
the kernel cannot answer for it: which of the graphs it may offer in a workspace
the caller can read or write (the workspace's view), and which workspace owns a
graph.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import unquote

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_of, workspace_of
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam.names import PLATFORM, encode_id, resource_name
from naas_abi_core.services.triple_store.iam_catalog import GRAPH, SERVICE

# Any graph IRI of a workspace stands for "a new graph there": roles and the
# workspace's own statements name ``graph/*``.
NEW_GRAPH = "urn:nexus:new-graph"


def graph_id(iri: str) -> str:
    """The canonical id of a graph, as its placement is keyed."""
    return encode_id(iri, "opaque")


def graph_name(iri: str, *, container: str | None = None) -> str:
    """The canonical name of a graph: in ``container`` (a workspace's) when given,
    else where IAM placed it (the platform when it did not)."""
    if container is None:
        container = runtime.iam().resolve_placement(SERVICE, graph_id(iri))
    return resource_name(SERVICE, GRAPH, iri, kind="opaque", container=container)


def allowed(action: str, iris: Iterable[str], *, user: Any) -> set[str]:
    """The graphs among ``iris`` the user may perform ``triple_store:<action>`` on,
    decided by IAM as ``api`` on behalf of the user (what the kernel decides)."""
    found = list(dict.fromkeys(iris))
    if not found:
        return set()
    names = {iri: graph_name(iri) for iri in found}
    with use_call_context(AUTHZ.context(user)):
        granted = set(runtime.iam().filter(f"{SERVICE}:{action}", names.values()).allowed)
    return {iri for iri, name in names.items() if name in granted}


def may_create(container: str, *, user: Any) -> bool:
    """Whether the user may create a graph in the workspace ``container``."""
    name = graph_name(NEW_GRAPH, container=container)
    with use_call_context(AUTHZ.context(user)):
        return runtime.iam().authorize(f"{SERVICE}:CreateGraph", name).allowed


def owned_by(workspace: str) -> set[str]:
    """The graphs IAM placed in ``workspace`` (exact placements, not prefixes)."""
    with as_service_account("api"):
        placements = runtime.iam().list_placements(SERVICE)
    return {
        unquote(placement.id_key)
        for placement in placements
        if workspace_of(placement.container) == workspace and not placement.id_key.endswith("*")
    }


def within(
    iris: Iterable[str],
    *,
    container: str,
    recorded: Mapping[str, str] = {},  # noqa: B006 - read only
) -> set[str]:
    """The graphs among ``iris`` a ``read_all`` of the workspace ``container`` may
    reach: the ones IAM placed in the workspace itself or in another workspace of
    its own organization, and the platform's (placed nowhere: nobody's data). A
    graph of another organization, or of a workspace in none (a personal
    workspace: someone else's), is never swept in; naming it is a right over it
    (see ``_graph_catalog``).

    ``recorded`` is ``{graph: container}`` for graphs the application graph
    records as a workspace's before IAM placed them (the boot pass places them
    after it applies assignments): they count as that workspace's."""
    with as_service_account("api"):
        placements = runtime.iam().list_placements(SERVICE)
    placed = dict(recorded)
    placed |= {unquote(p.id_key): p.container for p in placements if not p.id_key.endswith("*")}
    org = org_of(container)
    kept = set()
    for iri in iris:
        where = placed.get(iri)
        if where is None or where == PLATFORM:
            kept.add(iri)
        elif where == container or (org is not None and org_of(where) == org):
            kept.add(iri)
    return kept


def owners() -> dict[str, str]:
    """``{graph iri: workspace}`` for every graph IAM placed in a workspace."""
    with as_service_account("api"):
        placements = runtime.iam().list_placements(SERVICE)
    found: dict[str, str] = {}
    for placement in placements:
        workspace = workspace_of(placement.container)
        if workspace is not None and not placement.id_key.endswith("*"):
            found[unquote(placement.id_key)] = workspace
    return found

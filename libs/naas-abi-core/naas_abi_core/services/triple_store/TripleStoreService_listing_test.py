"""The triple store's graphs, listed for the policy builder as the caller
(``services/iam/AGENTS.md``, "Publishers and listing")."""

from __future__ import annotations

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.kernel_catalogs import (
    kernel_catalogs,
    register_kernel_listers,
)
from naas_abi_core.services.iam.names import resource_name
from naas_abi_core.services.iam.tests.iam_harness import NEXUS, IAMHarness, workspace
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded as OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import URIRef

WS1, WS2 = workspace("ws-1"), workspace("ws-2")


class _Bus:
    def publish_many(self, *_args, **_kwargs) -> None:
        return None


def _graph(iri: str, where: str) -> str:
    return resource_name("triple_store", "graph", iri, container=where)


def test_a_workspace_admin_lists_the_graphs_of_their_workspace(tmp_path):
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    with as_service_account("engine"):
        for catalog in kernel_catalogs():
            iam.register_catalog(catalog)
    iam._register_catalog(NEXUS)
    h = IAMHarness(iam)
    h.register("ws-1")
    h.register("ws-2")
    store = TripleStoreService(OxigraphEmbedded(str(tmp_path / "oxigraph")))
    store.set_services(IEngine.Services(iam=iam, bus=_Bus()))
    # Graphs created inside a workspace are placed there.
    for where, iri in ((WS1, "http://g/sales"), (WS1, "http://g/hr"), (WS2, "http://g/ops")):
        with as_service_account("api"), iam_inside(where):
            store.create_graph(URIRef(iri))
    assert register_kernel_listers(iam, [store, None]) == [("triple_store", "graph")]

    admin, stranger = h.user("admin"), h.user("stranger")
    h.attach(roles.ADMIN, admin.id, WS1)
    with h.as_(admin):
        page = iam.list_resources("triple_store", "graph", scope=WS1)
        assert page.listed
        assert [i.name for i in page.items] == [
            _graph("http://g/hr", WS1),
            _graph("http://g/sales", WS1),
        ]
        assert iam.list_resources("triple_store", "graph", scope=WS2).items == ()
        assert [i.id for i in iam.list_resources(
            "triple_store", "graph", scope=WS1, text="SAL"
        ).items] == ["http://g/sales"]
    with h.as_(stranger):
        assert iam.list_resources("triple_store", "graph", scope=WS1).items == ()


def iam_inside(container: str):
    from dataclasses import replace

    from naas_abi_core.engine.call_context import current_call_context, use_call_context

    return use_call_context(replace(current_call_context(), container=container))

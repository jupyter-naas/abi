"""Listing the existing resources of a type, as the caller (``AGENTS.md``,
"Publishers and listing")."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError
from naas_abi_core.services.iam.listing import (
    FunctionLister,
    ListedPage,
    ListedResource,
    ListerDirectory,
    ListingQuery,
    ResourceLister,
    page_of,
)
from naas_abi_core.services.iam.names import PLATFORM, resource_name
from naas_abi_core.services.iam.tests.iam_harness import (
    graph,
    name_in,
    org,
    statement,
    workspace,
)

WS1 = workspace("ws-1")
WS2 = workspace("ws-2")


def _graphs(*names: str) -> FunctionLister:
    """Every graph of ``names`` (``<ws>:<iri>``), as a triple store lists them."""

    def items(query: ListingQuery) -> list[ListedResource]:
        found = []
        for entry in names:
            ws, _, iri = entry.partition(":")
            name = resource_name(
                "triple_store", "graph", iri, container=workspace(ws)
            )
            found.append(ListedResource(name=name, id=iri, label=iri.upper()))
        return found

    return FunctionLister(items)


@pytest.fixture
def team(h):
    h.register("ws-1")
    h.register("ws-2")
    admin, stranger = h.user("admin"), h.user("stranger")
    h.attach(roles.ADMIN, admin.id, WS1)
    h.iam.register_lister(
        "triple_store", "graph", _graphs("ws-1:a", "ws-1:b", "ws-2:c", "ws-1:dd")
    )
    return admin, stranger


@pytest.fixture
def warnings() -> Iterator[list[str]]:
    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    yield seen
    logger.remove(sink)


def _names(page) -> list[str]:
    return [item.name for item in page.items]


def test_a_workspace_admin_lists_the_graphs_of_their_workspace_only(h, team):
    admin, stranger = team
    with h.as_(admin):
        page = h.iam.list_resources("triple_store", "graph", scope=WS1)
        assert page.listed
        assert _names(page) == [graph("a"), graph("b"), graph("dd")]
        # Another workspace: nothing of it, though the lister knows its graphs.
        assert h.iam.list_resources("triple_store", "graph", scope=WS2).items == ()
        # At the organisation or the platform: still only what they may list.
        assert _names(h.iam.list_resources("triple_store", "graph", scope=org())) == [
            graph("a"),
            graph("b"),
            graph("dd"),
        ]
        assert len(h.iam.list_resources("triple_store", "graph").items) == 3
    with h.as_(stranger):
        for scope in (WS1, WS2, org(), PLATFORM):
            page = h.iam.list_resources("triple_store", "graph", scope=scope)
            assert page.items == () and page.listed


def test_a_listing_pages_by_name_and_searches(h, team):
    admin, _ = team
    with h.as_(admin):
        first = h.iam.list_resources("triple_store", "graph", scope=WS1, limit=2)
        assert _names(first) == [graph("a"), graph("b")]
        assert first.next_cursor == graph("b")
        rest = h.iam.list_resources(
            "triple_store", "graph", scope=WS1, limit=2, cursor=first.next_cursor
        )
        assert _names(rest) == [graph("dd")] and rest.next_cursor is None
        # The search text matches the id or the label, case folded.
        assert _names(
            h.iam.list_resources("triple_store", "graph", scope=WS1, text="D")
        ) == [graph("dd")]
        assert h.iam.list_resources(
            "triple_store", "graph", scope=WS1, text="zz"
        ).items == ()
        # Below a container: that container.
        assert len(
            h.iam.list_resources("triple_store", "graph", scope=WS1 + "/*").items
        ) == 3


def test_what_a_lister_returns_outside_the_query_is_dropped(h):
    h.register("ws-1")
    admin = h.user("admin")
    h.attach(roles.ADMIN, admin.id, WS1)

    class Careless(ResourceLister):
        def list_resources(self, query: ListingQuery) -> ListedPage:
            return ListedPage(
                (
                    ListedResource(graph("a"), "a"),
                    ListedResource(name_in(WS1, "triple_store:view/v"), "v"),
                    ListedResource(graph("b", workspace="ws-9"), "b"),
                    ListedResource(graph("a"), "a"),
                )
            )

    h.iam.register_lister("triple_store", "graph", Careless())
    with h.as_(admin):
        page = h.iam.list_resources("triple_store", "graph", scope=WS1)
    assert _names(page) == [graph("a")]


def test_a_lister_that_fails_offers_its_type_as_wildcards_and_is_logged(
    h, team, warnings
):
    admin, _ = team

    class Broken(ResourceLister):
        def list_resources(self, query: ListingQuery) -> ListedPage:
            raise RuntimeError("store down")

    h.iam.register_lister("triple_store", "graph", Broken())
    with h.as_(admin):
        page = h.iam.list_resources("triple_store", "graph", scope=WS1)
    assert page.listed is False and page.items == ()
    assert any("triple_store:graph" in w and "store down" in w for w in warnings)


def test_a_type_with_no_lister_is_offered_as_wildcards(h):
    h.register("ws-1")
    admin = h.user("admin")
    h.attach(roles.ADMIN, admin.id, WS1)
    with h.as_(admin):
        page = h.iam.list_resources("triple_store", "graph", scope=WS1)
    assert page.listed is False and page.items == ()
    assert not h.iam.has_lister("triple_store", "graph")


def test_an_unknown_service_or_type_is_not_found(h):
    with as_service_account("engine"):
        with pytest.raises(IAMNotFoundError):
            h.iam.list_resources("nope", "graph")
        with pytest.raises(IAMNotFoundError):
            h.iam.list_resources("triple_store", "nope")
        with pytest.raises(ValueError):
            h.iam.list_resources("triple_store", "graph", scope="abi:o:w")
    with pytest.raises(IAMNotFoundError):
        h.iam.register_lister("nope", "graph", _graphs())


def test_a_type_with_no_list_action_is_listed_to_whoever_holds_any_of_its_actions(
    h,
):
    reports = ActionCatalog(
        service="reports",
        version=1,
        resource_types=(ResourceType("report", id="opaque"),),
        actions=(ActionSpec("Export", "read", ("report",)),),
    )
    h.iam._register_catalog(reports)
    h.register("ws-1")
    reader, other = h.user("reader"), h.user("other")
    h.grant(reader.id, statement("Allow", ["reports:Export"], [name_in(WS1, "reports:report/r1")]))

    def items(query: ListingQuery) -> list[ListedResource]:
        return [
            ListedResource(name_in(WS1, f"reports:report/{r}"), r) for r in ("r1", "r2")
        ]

    h.iam.register_lister("reports", "report", FunctionLister(items))
    with h.as_(reader):
        assert _names(h.iam.list_resources("reports", "report", scope=WS1)) == [
            name_in(WS1, "reports:report/r1")
        ]
    with h.as_(other):
        assert h.iam.list_resources("reports", "report", scope=WS1).items == ()


def test_iam_lists_containers_from_its_registry(h):
    h.register("ws-1")
    h.register("ws-2")
    h.register("ws-3", org_id="org-2")
    admin = h.user("admin")
    h.attach(roles.ADMIN, admin.id, org() + "/*")
    with h.as_(admin):
        page = h.iam.list_resources("nexus", "workspace", scope=org())
        assert page.listed
        assert _names(page) == [WS1, WS2]
        assert [i.id for i in page.items] == ["ws-1", "ws-2"]
        # Not another organisation's.
        assert h.iam.list_resources("nexus", "workspace", scope=org("org-2")).items == ()
    assert h.iam.has_lister("nexus", "workspace")


def test_a_container_lister_labels_the_registry_and_never_adds_to_it(h, warnings):
    h.register("ws-1")
    admin = h.user("admin")
    h.attach(roles.ADMIN, admin.id, org() + "/*")

    def items(query: ListingQuery) -> list[ListedResource]:
        return [
            ListedResource(WS1, "ws-1", label="Sales"),
            # Not registered: dropped.
            ListedResource(workspace("ws-9"), "ws-9", label="Ghost"),
        ]

    h.iam.register_lister("nexus", "workspace", FunctionLister(items))
    with h.as_(admin):
        page = h.iam.list_resources("nexus", "workspace", scope=org())
    assert [(i.name, i.label) for i in page.items] == [(WS1, "Sales")]

    class Broken(ResourceLister):
        def list_resources(self, query: ListingQuery) -> ListedPage:
            raise RuntimeError("db down")

    h.iam.register_lister("nexus", "workspace", Broken())
    with h.as_(admin):
        page = h.iam.list_resources("nexus", "workspace", scope=org())
    # The registry answers instead.
    assert page.listed and _names(page) == [WS1]
    assert any("db down" in w for w in warnings)


def test_iam_lists_the_one_resource_of_a_singleton_type(h):
    settings = ActionCatalog(
        service="settings",
        version=1,
        resource_types=(
            ResourceType("billing", id="singleton"),
            ResourceType("system", id="singleton", placement="platform"),
        ),
        actions=(
            ActionSpec("GetBilling", "read", ("billing",)),
            ActionSpec("GetSystem", "read", ("system",)),
        ),
    )
    h.iam._register_catalog(settings)
    h.first_party_may("settings")
    h.register("ws-1")
    admin = h.user("admin")
    h.attach(roles.ADMIN, admin.id, WS1)
    with h.as_(admin):
        assert _names(h.iam.list_resources("settings", "billing", scope=WS1)) == [
            name_in(WS1, "settings:billing/-")
        ]
        # A platform singleton is at the platform only.
        assert h.iam.list_resources("settings", "system", scope=WS1).items == ()
    with as_service_account("engine"):
        assert _names(h.iam.list_resources("settings", "system")) == [
            "abi:settings:system/-"
        ]


def test_the_module_catalog_lists_one_module_when_asked(h):
    h.iam._register_catalog(module_scopes.CATALOG)
    h.register("ws-1")
    user = h.user("bob")
    h.grant(
        user.id,
        statement("Allow", ["module:UseAgent"], [WS1 + "/module:agent/*"]),
    )

    def items(query: ListingQuery) -> list[ListedResource]:
        return [
            ListedResource(
                module_scopes.scope_resource("agent", module, name, container=query.container),
                f"{module}/{name}",
                label=name,
            )
            for module, name in (("p", "a"), ("p", "b"), ("m", "x"))
        ]

    h.iam.register_lister("module", "agent", FunctionLister(items))
    with h.as_(user):
        every = h.iam.list_resources("module", "agent", scope=WS1)
        assert [i.id for i in every.items] == ["m/x", "p/a", "p/b"]
        only_p = h.iam.list_resources("module", "agent", scope=WS1, module="p")
        assert [i.id for i in only_p.items] == ["p/a", "p/b"]


def test_a_remote_module_type_is_asked_through_the_directory(h):
    crm = ActionCatalog(
        service="acme_crm",
        version=1,
        module="acme.crm",
        resource_types=(ResourceType("deal", id="opaque", module_scope=True),),
        actions=(ActionSpec("ListDeals", "list", ("deal",)),),
    )
    with as_service_account("engine"):
        h.iam.register_catalog(crm)
    h.register("ws-1")
    user = h.user("bob")
    h.grant(user.id, statement("Allow", ["acme_crm:ListDeals"], [WS1 + "/*"]))
    asked: list[tuple[str, str, str]] = []

    class Directory(ListerDirectory):
        def lister(self, module, service, type):
            asked.append((module, service, type))
            return FunctionLister(
                lambda query: [ListedResource(name_in(WS1, "acme_crm:deal/d1"), "d1")]
            )

    assert not h.iam.has_lister("acme_crm", "deal")
    h.iam.remote_listers = Directory()
    assert h.iam.has_lister("acme_crm", "deal")
    with h.as_(user):
        page = h.iam.list_resources("acme_crm", "deal", scope=WS1)
    assert _names(page) == [name_in(WS1, "acme_crm:deal/d1")]
    assert asked == [("acme.crm", "acme_crm", "deal")]


def test_a_listing_examines_a_bounded_number_of_candidates(h, monkeypatch):
    from naas_abi_core.services.iam import listing

    monkeypatch.setattr(listing, "MAX_EXAMINED", 300)
    h.register("ws-1")
    user = h.user("bob")
    # Allowed only the last of many.
    h.grant(user.id, statement("Allow", ["triple_store:ListGraphs"], [graph("z999")]))
    names = [f"ws-1:g{i:04d}" for i in range(1000)] + ["ws-1:z999"]
    h.iam.register_lister("triple_store", "graph", _graphs(*names))
    with h.as_(user):
        page = h.iam.list_resources("triple_store", "graph", scope=WS1)
        assert page.items == () and page.next_cursor is not None
        seen = []
        while page.next_cursor is not None:
            page = h.iam.list_resources(
                "triple_store", "graph", scope=WS1, cursor=page.next_cursor
            )
            seen += _names(page)
    assert seen == [graph("z999")]


def test_page_of_pages_an_in_memory_list():
    items = [ListedResource(graph(n), n, label=n) for n in ("c", "a", "b", "a")]
    page = page_of(items, ListingQuery("triple_store", "graph", WS1, limit=2))
    assert [i.id for i in page.items] == ["a", "b"] and page.more
    page = page_of(
        items, ListingQuery("triple_store", "graph", WS1, after=graph("b"), limit=2)
    )
    assert [i.id for i in page.items] == ["c"] and not page.more
    assert page_of(items, ListingQuery("triple_store", "graph", WS2)).items == ()

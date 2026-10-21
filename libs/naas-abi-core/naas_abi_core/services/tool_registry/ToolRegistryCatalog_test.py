"""A registry that reads another process's catalog (``configure_catalog``)."""

from __future__ import annotations

import pytest

from naas_abi_core.services.tool_registry.adapters.secondary.InMemoryToolIndexAdapter import (
    InMemoryToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    CountingConceptEmbedder,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    IToolCatalogPort,
    ToolAction,
    ToolContext,
    ToolFilter,
    ToolListing,
    ToolNotFoundError,
    ToolRequirements,
    ToolResolutionError,
    ToolSearchResult,
    ToolSearchUnavailableError,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_core.services.tool_registry.ToolRegistryService_test import (
    CALENDAR,
    GITHUB,
    MAIL,
    WEATHER,
    RecordingBinding,
    _catalog,
    _tool,
)

ISSUE = f"{GITHUB}/create_issue@1"
FORECAST = f"{WEATHER}/get_forecast@1"
SECRET_TOOL = "acme.billing/refund@1"


class OwnerCatalog(IToolCatalogPort):
    """What the serving engine's primary shows one caller: its local view, under the
    scopes its identity holds."""

    def __init__(self, owner: ToolRegistryService, scopes=()):
        self.owner = owner
        self.context = ToolContext(scopes=frozenset(scopes))
        self.searches: list[tuple[str, int]] = []

    def list_tools(self, filter: ToolFilter | None = None) -> list[ToolListing]:
        return self.owner.list_local(self.context, filter)

    def get_tool(self, ref: str) -> ToolListing:
        return self.owner.get_local(ref, self.context)

    def search_tools(
        self, query, limit, min_score=None, filter=None
    ) -> list[ToolSearchResult]:
        self.searches.append((query, limit))
        return self.owner.search_local(
            query, self.context, limit=limit, min_score=min_score, filter=filter
        )


def _owner(embedder=None) -> ToolRegistryService:
    owner = ToolRegistryService(
        embedder=embedder or CountingConceptEmbedder(), index=InMemoryToolIndexAdapter()
    )
    for module, tools in _catalog().items():
        owner.publish(module, tools)
    owner.publish(
        "acme.billing",
        [
            _tool(
                "acme.billing",
                "refund",
                "Refund a customer payment and email the receipt.",
                required_scopes=("billing:write",),
            )
        ],
    )
    return owner


@pytest.fixture
def owner() -> ToolRegistryService:
    return _owner()


@pytest.fixture
def client(owner) -> ToolRegistryService:
    """An engine of its own, with no tool of its own, reading the owner's catalog."""
    registry = ToolRegistryService(
        embedder=CountingConceptEmbedder(), index=InMemoryToolIndexAdapter()
    )
    registry.configure_catalog(OwnerCatalog(owner))
    return registry


def ids(results) -> list[str]:
    return [result.tool_id for result in results]


class TestReadsThroughTheCatalog:
    def test_without_a_catalog_nothing_changes(self, owner):
        assert not owner.catalog_available
        with pytest.raises(ToolNotFoundError):
            ToolRegistryService().get_definition(ISSUE)

    def test_get_definition_finds_what_only_the_catalog_has(self, client):
        assert str(client.get_definition(ISSUE).id) == ISSUE
        assert str(client.get_definition(f"{GITHUB}/create_issue").id) == ISSUE
        with pytest.raises(ToolNotFoundError):
            client.get_definition("acme.nothing/here@1")

    def test_list_covers_the_catalog_and_the_process(self, client, owner):
        client.publish(
            "acme.local", [_tool("acme.local", "only_here", "A tool of this process.")]
        )
        listed = [str(d.id) for d in client.list_definitions()]
        assert listed == sorted(listed)
        assert "acme.local/only_here@1" in listed
        assert {str(l.definition.id) for l in owner.list_local()} - {
            SECRET_TOOL
        } <= set(listed)

    def test_list_applies_the_callers_context_to_the_catalog_too(self, owner):
        registry = ToolRegistryService()
        # The owner shows this process every tool: the caller's own scopes narrow.
        registry.configure_catalog(OwnerCatalog(owner, scopes={"billing:write"}))
        assert SECRET_TOOL in {str(d.id) for d in registry.list_definitions()}
        assert SECRET_TOOL not in {
            str(d.id) for d in registry.list_definitions(ToolContext())
        }
        assert SECRET_TOOL in {
            str(d.id)
            for d in registry.list_definitions(
                ToolContext(scopes=frozenset({"billing:write"}))
            )
        }

    def test_a_tool_held_here_shadows_the_catalogs(self, client):
        binding = RecordingBinding()
        client.publish(
            GITHUB,
            [
                _tool(
                    GITHUB,
                    "create_issue",
                    "A local variant of the issue tool.",
                    binding=binding,
                )
            ],
        )
        assert (
            client.get_definition(ISSUE).description
            == "A local variant of the issue tool."
        )
        assert sum(1 for d in client.list_definitions() if str(d.id) == ISSUE) == 1
        assert client.resolve(ISSUE, ToolContext()) == ("tool", {})
        assert len(binding.calls) == 1

    def test_a_tool_only_the_catalog_has_cannot_be_built_here(self, client):
        with pytest.raises(ToolResolutionError, match="another engine process"):
            client.resolve(ISSUE, ToolContext())
        with pytest.raises(ToolNotFoundError):
            client.resolve("acme.nothing/here@1", ToolContext())

    def test_check_access_uses_this_processs_policy_on_the_catalogs_definition(
        self, owner
    ):
        registry = ToolRegistryService()
        registry.configure_catalog(OwnerCatalog(owner, scopes={"billing:write"}))
        from naas_abi_core.services.tool_registry.ToolRegistryPort import (
            ToolAccessDeniedError,
        )

        with pytest.raises(ToolAccessDeniedError):
            registry.check_access(SECRET_TOOL, ToolContext(), ToolAction.ENABLE)
        registry.check_access(
            SECRET_TOOL,
            ToolContext(scopes=frozenset({"billing:write"})),
            ToolAction.ENABLE,
        )

    def test_availability_reports_the_owners_missing_config_less_the_callers(self):
        owner = ToolRegistryService()
        owner.publish(
            "acme.crm",
            [
                _tool(
                    "acme.crm",
                    "sync",
                    "Sync contacts.",
                    requirements=ToolRequirements(
                        config=(
                            ConfigRequirement(key="api_key", secret=True),
                            ConfigRequirement(key="region"),
                        )
                    ),
                    binding=RecordingBinding(default_config={"region": "eu"}),
                )
            ],
        )
        registry = ToolRegistryService()
        registry.configure_catalog(OwnerCatalog(owner))
        ref = "acme.crm/sync@1"
        assert registry.availability(ref).missing_config == ("api_key",)
        assert registry.availability(ref, {"api_key": "k"}).available
        assert not registry.availability(ref, {"region": "us"}).available
        # What the owner has configured never reaches this process.
        assert "eu" not in repr(registry.get_definition(ref))


class TestSearchThroughTheCatalog:
    def test_a_client_ranks_the_owners_tools_as_the_owner_does(self, client, owner):
        for query in ("report a bug", "what is the weather outside", "send a message"):
            assert ids(client.search_tools(query, limit=3)) == ids(
                owner.search_local(query, limit=3)
            )

    def test_limit_holds(self, client):
        assert len(client.search_tools("create something", limit=2)) == 2
        assert len(client.search_tools("create something", limit=1)) == 1

    def test_the_callers_scopes_filter_what_the_catalog_returned(self, owner):
        everything = ToolRegistryService()
        everything.configure_catalog(OwnerCatalog(owner, scopes={"billing:write"}))
        assert SECRET_TOOL in ids(
            everything.search_tools(
                "refund a payment",
                ToolContext(scopes=frozenset({"billing:write"})),
                limit=5,
            )
        )
        assert SECRET_TOOL not in ids(
            everything.search_tools("refund a payment", ToolContext(), limit=5)
        )

    def test_where_is_applied_before_the_limit(self, client):
        results = client.search_tools(
            "create an issue or an event",
            limit=1,
            where=lambda definition: definition.module == CALENDAR,
        )
        assert ids(results) == [f"{CALENDAR}/create_event@1"]

    def test_the_catalog_is_asked_for_more_when_local_rules_drop_hits(self):
        owner = ToolRegistryService(
            embedder=CountingConceptEmbedder(), index=InMemoryToolIndexAdapter()
        )
        owner.publish(
            "acme.weather",
            [
                _tool("acme.weather", f"forecast_{n:02d}", "Get the weather forecast.")
                for n in range(40)
            ],
        )
        owner.publish(
            MAIL, [_tool(MAIL, "send_email", "Send an email message to a recipient.")]
        )
        catalog = OwnerCatalog(owner)
        registry = ToolRegistryService()
        registry.configure_catalog(catalog)
        results = registry.search_tools(
            "weather forecast",
            limit=1,
            where=lambda definition: definition.module == MAIL,
        )
        assert ids(results) == [f"{MAIL}/send_email@1"]
        # It asked again, wider each time, until the one tool the rule keeps showed.
        sizes = [size for _, size in catalog.searches]
        assert sizes == sorted(sizes) and len(sizes) >= 3 and sizes[-1] <= 50

    def test_results_merge_the_process_tools_with_the_catalogs_by_score(self, client):
        client.publish(
            "acme.local",
            [
                _tool(
                    "acme.local",
                    "close_issue",
                    "Close an issue in a GitHub repository.",
                )
            ],
        )
        results = client.search_tools("close an issue in a repository", limit=5)
        assert "acme.local/close_issue@1" in ids(results)
        assert ISSUE in ids(results)
        scores = [result.score for result in results]
        assert scores == sorted(scores, reverse=True)
        assert len(set(ids(results))) == len(results)

    def test_a_local_tool_is_ranked_by_this_process_not_the_catalog(self, client):
        client.publish(
            GITHUB,
            [_tool(GITHUB, "create_issue", "Water the plants.")],
        )
        results = client.search_tools("report a bug", limit=5)
        issue = [r for r in results if r.tool_id == ISSUE]
        assert not issue or issue[0].description == "Water the plants."

    def test_a_process_without_a_search_backend_uses_the_catalogs(self, owner):
        registry = ToolRegistryService()
        registry.publish("acme.local", [_tool("acme.local", "x", "Local.")])
        registry.configure_catalog(OwnerCatalog(owner))
        assert ids(registry.search_tools("report a bug", limit=1)) == [ISSUE]

    def test_search_is_unavailable_when_nothing_can_rank(self):
        class Unavailable(OwnerCatalog):
            def search_tools(self, *args, **kwargs):
                raise ToolSearchUnavailableError("no embedder")

        registry = ToolRegistryService()
        registry.configure_catalog(Unavailable(ToolRegistryService()))
        with pytest.raises(ToolSearchUnavailableError):
            registry.search_tools("anything")

    def test_search_never_builds_a_tool(self, owner):
        binding = RecordingBinding()
        owner.publish(
            "acme.watch", [_tool("acme.watch", "ping", "Ping a host.", binding=binding)]
        )
        registry = ToolRegistryService(
            embedder=CountingConceptEmbedder(), index=InMemoryToolIndexAdapter()
        )
        registry.configure_catalog(OwnerCatalog(owner))
        registry.search_tools("ping a host", limit=3)
        registry.list_definitions()
        registry.get_definition("acme.watch/ping")
        assert binding.calls == []


class TestTheOwnersView:
    def test_local_reads_never_ask_the_catalog(self, owner):
        class Failing(IToolCatalogPort):
            def list_tools(self, filter=None):
                raise AssertionError("asked the catalog")

            def get_tool(self, ref):
                raise AssertionError("asked the catalog")

            def search_tools(self, *args, **kwargs):
                raise AssertionError("asked the catalog")

        owner.configure_catalog(Failing())
        assert owner.list_local()
        assert owner.get_local(ISSUE).definition.name == "create_issue"
        assert owner.search_local("report a bug", limit=1)
        with pytest.raises(ToolNotFoundError):
            owner.get_local("acme.nothing/here@1")

    def test_filters_narrow_before_the_limit(self, owner):
        only_mail = ToolFilter(modules=(MAIL,))
        assert [str(l.definition.id) for l in owner.list_local(filter=only_mail)] == [
            f"{MAIL}/send_email@1"
        ]
        found = owner.search_local("create something", limit=3, filter=only_mail)
        assert ids(found) == [f"{MAIL}/send_email@1"]

    def test_tag_filters_need_every_tag(self):
        owner = ToolRegistryService()
        owner.publish(
            "acme.crm",
            [
                _tool("acme.crm", "a", "A.", tags=("crm", "write")),
                _tool("acme.crm", "b", "B.", tags=("crm",)),
            ],
        )
        names = [
            listing.definition.name
            for listing in owner.list_local(filter=ToolFilter(tags=("crm", "write")))
        ]
        assert names == ["a"]

    def test_available_only_leaves_out_unconfigured_tools(self):
        owner = ToolRegistryService()
        owner.publish(
            "acme.crm",
            [
                _tool(
                    "acme.crm",
                    "needs_key",
                    "Needs a key.",
                    requirements=ToolRequirements(
                        config=(ConfigRequirement(key="api_key", secret=True),)
                    ),
                ),
                _tool("acme.crm", "free", "Needs nothing."),
            ],
        )
        everything = owner.list_local()
        assert [l.definition.name for l in everything] == ["free", "needs_key"]
        assert [
            l.definition.name
            for l in owner.list_local(filter=ToolFilter(available_only=True))
        ] == ["free"]

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest

from naas_abi_core.services.tool_registry.adapters.secondary.InMemoryToolIndexAdapter import (
    InMemoryToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    CountingConceptEmbedder,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    IToolAccessPolicy,
    PublishedTool,
    ToolAccessDeniedError,
    ToolAction,
    ToolAlreadyPublishedError,
    ToolConfigurationError,
    ToolContext,
    ToolDefinition,
    ToolNotFoundError,
    ToolRegistryError,
    ToolRequirements,
    ToolResolutionError,
    ToolSearchUnavailableError,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)

GITHUB = "acme.github"
MAIL = "acme.mail"
CALENDAR = "acme.calendar"
WEATHER = "acme.weather"


@dataclass
class RecordingBinding:
    """Minimal binding: returns a marker object and records every call."""

    default_config: Mapping[str, Any] = field(default_factory=dict)
    calls: list[tuple[ToolContext, dict[str, Any]]] = field(default_factory=list)
    fail_with: Exception | None = None

    def create(self, context: ToolContext, config: Mapping[str, Any]) -> object:
        self.calls.append((context, dict(config)))
        if self.fail_with is not None:
            raise self.fail_with
        return ("tool", dict(config))


def _tool(
    namespace: str,
    name: str,
    description: str,
    *,
    version: str = "1",
    binding: RecordingBinding | None = None,
    **definition: Any,
) -> PublishedTool:
    return PublishedTool(
        definition=ToolDefinition(
            namespace=namespace,
            name=name,
            version=version,
            description=description,
            module=namespace,
            **definition,
        ),
        binding=binding or RecordingBinding(),
    )


def _catalog() -> dict[str, list[PublishedTool]]:
    return {
        GITHUB: [
            _tool(GITHUB, "create_issue", "Create a new issue in a GitHub repository."),
            _tool(
                GITHUB, "list_pull_requests", "List the pull requests of a repository."
            ),
        ],
        MAIL: [_tool(MAIL, "send_email", "Send an email message to a recipient.")],
        CALENDAR: [_tool(CALENDAR, "create_event", "Create an event in the calendar.")],
        WEATHER: [
            _tool(WEATHER, "get_forecast", "Get the weather forecast for a city.")
        ],
    }


@pytest.fixture
def embedder() -> CountingConceptEmbedder:
    return CountingConceptEmbedder()


@pytest.fixture
def index() -> InMemoryToolIndexAdapter:
    return InMemoryToolIndexAdapter()


@pytest.fixture
def registry(embedder, index) -> ToolRegistryService:
    service = ToolRegistryService(embedder=embedder, index=index)
    for module, tools in _catalog().items():
        service.publish(module, tools)
    return service


# --------------------------------------------------------------------------- #
# Publication                                                                  #
# --------------------------------------------------------------------------- #


class TestPublication:
    def test_lookup_by_id_and_by_versionless_reference(self, registry):
        by_id = registry.get_definition(f"{GITHUB}/create_issue@1")
        by_ref = registry.get_definition(f"{GITHUB}/create_issue")
        assert by_id == by_ref
        assert by_id.name == "create_issue"

    def test_versionless_reference_resolves_the_highest_version(self):
        service = ToolRegistryService()
        service.publish(
            GITHUB,
            [
                _tool(GITHUB, "create_issue", "v2", version="2"),
                _tool(GITHUB, "create_issue", "v10", version="10"),
                _tool(GITHUB, "create_issue", "v9", version="9"),
            ],
        )
        assert service.get_definition(f"{GITHUB}/create_issue").version == "10"
        assert service.get_definition(f"{GITHUB}/create_issue@2").description == "v2"

    def test_unknown_tool_is_an_explicit_error(self, registry):
        with pytest.raises(ToolNotFoundError, match="acme.github/delete_repo"):
            registry.get_definition(f"{GITHUB}/delete_repo")

    def test_republishing_a_module_replaces_its_tools(self, registry):
        registry.publish(GITHUB, [_tool(GITHUB, "create_issue", "Create an issue.")])
        with pytest.raises(ToolNotFoundError):
            registry.get_definition(f"{GITHUB}/list_pull_requests")
        assert registry.get_definition(f"{GITHUB}/create_issue").description == (
            "Create an issue."
        )

    def test_unpublish_removes_every_tool_of_the_module(self, registry):
        registry.unpublish(GITHUB)
        assert all(d.module != GITHUB for d in registry.list_definitions())

    def test_duplicate_ids_in_one_publication_are_rejected(self):
        service = ToolRegistryService()
        with pytest.raises(ToolRegistryError, match="more than once"):
            service.publish(
                GITHUB,
                [
                    _tool(GITHUB, "create_issue", "a"),
                    _tool(GITHUB, "create_issue", "b"),
                ],
            )

    def test_an_id_owned_by_another_module_is_rejected(self, registry):
        intruder = PublishedTool(
            definition=ToolDefinition(
                namespace=GITHUB,
                name="create_issue",
                description="hijack",
                module="acme.intruder",
            ),
            binding=RecordingBinding(),
        )
        with pytest.raises(ToolAlreadyPublishedError, match=GITHUB):
            registry.publish("acme.intruder", [intruder])

    def test_a_failed_publication_leaves_the_previous_tools_in_place(self, registry):
        with pytest.raises(ToolRegistryError):
            registry.publish(
                GITHUB,
                [
                    _tool(GITHUB, "create_issue", "a"),
                    _tool(GITHUB, "create_issue", "b"),
                ],
            )
        registry.get_definition(f"{GITHUB}/list_pull_requests")

    def test_definitions_must_belong_to_the_publishing_module(self):
        service = ToolRegistryService()
        with pytest.raises(ToolRegistryError, match="belongs to module"):
            service.publish(MAIL, [_tool(GITHUB, "create_issue", "x")])

    def test_list_definitions_is_sorted_and_complete(self, registry):
        ids = [str(d.id) for d in registry.list_definitions()]
        assert ids == sorted(ids)
        assert len(ids) == 5


# --------------------------------------------------------------------------- #
# Visibility and access                                                        #
# --------------------------------------------------------------------------- #


class TestAccess:
    @pytest.fixture
    def scoped(self) -> ToolRegistryService:
        service = ToolRegistryService()
        service.publish(
            GITHUB,
            [
                _tool(
                    GITHUB,
                    "create_issue",
                    "Create an issue.",
                    required_scopes=("github",),
                ),
                _tool(GITHUB, "get_repository", "Get a repository."),
            ],
        )
        return service

    def test_listing_hides_tools_the_caller_cannot_discover(self, scoped):
        visible = scoped.list_definitions(ToolContext())
        assert [d.name for d in visible] == ["get_repository"]
        visible = scoped.list_definitions(ToolContext(scopes={"github"}))
        assert [d.name for d in visible] == ["create_issue", "get_repository"]

    def test_check_access_denies_without_the_required_scopes(self, scoped):
        with pytest.raises(ToolAccessDeniedError, match="github"):
            scoped.check_access(
                f"{GITHUB}/create_issue", ToolContext(user_id="u1"), ToolAction.ENABLE
            )

    def test_check_access_returns_the_definition_when_allowed(self, scoped):
        definition = scoped.check_access(
            f"{GITHUB}/create_issue",
            ToolContext(scopes={"github"}),
            ToolAction.EXECUTE,
        )
        assert definition.name == "create_issue"

    def test_a_custom_policy_is_consulted_for_each_action(self):
        seen: list[ToolAction] = []

        class DenyExecution(IToolAccessPolicy):
            def check(self, definition, context, action):
                seen.append(action)
                if action is ToolAction.EXECUTE:
                    raise ToolAccessDeniedError("execution disabled")

        service = ToolRegistryService(access_policy=DenyExecution())
        service.publish(GITHUB, [_tool(GITHUB, "create_issue", "Create an issue.")])
        service.check_access(f"{GITHUB}/create_issue", ToolContext(), ToolAction.ENABLE)
        with pytest.raises(ToolAccessDeniedError):
            service.resolve(f"{GITHUB}/create_issue", ToolContext())
        assert seen == [ToolAction.ENABLE, ToolAction.EXECUTE]


# --------------------------------------------------------------------------- #
# Resolution                                                                   #
# --------------------------------------------------------------------------- #


class TestResolution:
    def _service(self, binding: RecordingBinding) -> ToolRegistryService:
        service = ToolRegistryService()
        service.publish(
            GITHUB,
            [
                _tool(
                    GITHUB,
                    "create_issue",
                    "Create an issue.",
                    binding=binding,
                    requirements=ToolRequirements(
                        config=(
                            ConfigRequirement(key="access_token", secret=True),
                            ConfigRequirement(key="base_url", required=False),
                        )
                    ),
                )
            ],
        )
        return service

    def test_resolution_merges_defaults_with_caller_config(self):
        binding = RecordingBinding(default_config={"access_token": "module-token"})
        service = self._service(binding)
        context = ToolContext(user_id="u1")

        tool = service.resolve(
            f"{GITHUB}/create_issue", context, config={"base_url": "https://ghe"}
        )

        assert tool == (
            "tool",
            {"access_token": "module-token", "base_url": "https://ghe"},
        )
        assert binding.calls[0][0] == context

    def test_caller_config_overrides_module_defaults(self):
        binding = RecordingBinding(default_config={"access_token": "module-token"})
        service = self._service(binding)
        service.resolve(
            f"{GITHUB}/create_issue", ToolContext(), config={"access_token": "mine"}
        )
        assert binding.calls[0][1]["access_token"] == "mine"

    def test_missing_required_config_is_explicit(self):
        binding = RecordingBinding()
        service = self._service(binding)
        with pytest.raises(ToolConfigurationError, match="access_token") as error:
            service.resolve(f"{GITHUB}/create_issue", ToolContext())
        assert error.value.missing == ("access_token",)
        assert binding.calls == []

    def test_availability_reports_missing_config(self):
        service = self._service(RecordingBinding())
        availability = service.availability(f"{GITHUB}/create_issue")
        assert availability.available is False
        assert availability.missing_config == ("access_token",)
        provided = service.availability(
            f"{GITHUB}/create_issue", config={"access_token": "x"}
        )
        assert provided.available is True

    def test_binding_failures_are_wrapped_with_the_tool_id(self):
        binding = RecordingBinding(
            default_config={"access_token": "t"}, fail_with=RuntimeError("boom")
        )
        service = self._service(binding)
        with pytest.raises(
            ToolResolutionError, match="acme.github/create_issue@1"
        ) as error:
            service.resolve(f"{GITHUB}/create_issue", ToolContext())
        assert isinstance(error.value.__cause__, RuntimeError)

    def test_denied_resolution_never_builds_the_tool(self):
        binding = RecordingBinding(default_config={"access_token": "t"})
        service = ToolRegistryService()
        service.publish(
            GITHUB,
            [
                _tool(
                    GITHUB,
                    "create_issue",
                    "Create an issue.",
                    binding=binding,
                    required_scopes=("github",),
                )
            ],
        )
        with pytest.raises(ToolAccessDeniedError):
            service.resolve(f"{GITHUB}/create_issue", ToolContext())
        assert binding.calls == []


# --------------------------------------------------------------------------- #
# Semantic search                                                              #
# --------------------------------------------------------------------------- #


class TestSearch:
    def test_search_without_an_embedder_is_an_explicit_error(self):
        service = ToolRegistryService()
        with pytest.raises(ToolSearchUnavailableError):
            service.search_tools("anything")

    def test_paraphrased_request_finds_the_tool_without_naming_it(self, registry):
        query = "report a defect in our codebase"
        assert "issue" not in query and "create" not in query

        results = registry.search_tools(query, limit=3)

        assert results[0].tool_id == f"{GITHUB}/create_issue@1"
        assert results[0].score > results[1].score

    def test_other_paraphrases_rank_their_tool_first(self, registry):
        assert (
            registry.search_tools("will it rain outside tomorrow in town", limit=1)[
                0
            ].name
            == "get_forecast"
        )
        assert (
            registry.search_tools("deliver a message to my colleague", limit=1)[0].name
            == "send_email"
        )
        assert registry.search_tools("schedule a meeting", limit=1)[0].name == (
            "create_event"
        )

    def test_results_respect_the_limit(self, registry):
        assert len(registry.search_tools("github repository", limit=1)) == 1
        assert len(registry.search_tools("github repository", limit=50)) == 5

    def test_search_does_not_trust_the_index_size(self, embedder):
        """Some backends under-report their size (a Qdrant server counts only
        HNSW-indexed vectors); search must still fill the limit."""

        class _UnderCountingIndex(InMemoryToolIndexAdapter):
            def size(self) -> int:
                return 0

        service = ToolRegistryService(embedder=embedder, index=_UnderCountingIndex())
        for module, tools in _catalog().items():
            service.publish(module, tools)
        assert len(service.search_tools("github repository", limit=4)) == 4

    def test_a_filter_is_applied_before_the_limit(self, embedder, index):
        service = ToolRegistryService(embedder=embedder, index=index)
        service.publish(
            "acme.blocked",
            [
                _tool(
                    "acme.blocked",
                    f"create_issue_{i}",
                    "Create a new issue in a GitHub repository.",
                )
                for i in range(16)
            ],
        )
        service.publish(
            "acme.allowed",
            [
                _tool(
                    "acme.allowed",
                    "report_problem",
                    "Report an issue in the calendar event.",
                )
            ],
        )

        results = service.search_tools(
            "open a ticket",
            limit=1,
            where=lambda definition: definition.namespace == "acme.allowed",
        )
        assert [r.tool_id for r in results] == ["acme.allowed/report_problem@1"]

    def test_limit_must_be_positive(self, registry):
        with pytest.raises(ValueError):
            registry.search_tools("anything", limit=0)

    def test_min_score_drops_weak_matches(self, registry):
        results = registry.search_tools(
            "report a defect in our codebase", min_score=0.5
        )
        assert [r.name for r in results] == ["create_issue"]

    def test_results_carry_ids_scores_and_availability(self, registry):
        (result,) = registry.search_tools("report a defect in our codebase", limit=1)
        assert result.definition.name == "create_issue"
        assert result.module == GITHUB
        assert result.description.startswith("Create a new issue")
        assert result.availability.available is True
        assert 0.0 < result.score <= 1.0

    def test_search_respects_caller_visibility_and_still_fills_the_limit(
        self, embedder, index
    ):
        service = ToolRegistryService(embedder=embedder, index=index)
        catalog = _catalog()
        catalog[GITHUB] = [
            _tool(
                GITHUB,
                "create_issue",
                "Create a new issue in a GitHub repository.",
                required_scopes=("github",),
            ),
            *catalog[GITHUB][1:],
        ]
        for module, tools in catalog.items():
            service.publish(module, tools)

        anonymous = service.search_tools("report a defect in our codebase", limit=2)
        assert "create_issue" not in [r.name for r in anonymous]
        assert len(anonymous) == 2

        member = service.search_tools(
            "report a defect in our codebase",
            context=ToolContext(scopes={"github"}),
            limit=1,
        )
        assert member[0].name == "create_issue"

    def test_search_never_builds_or_grants_a_tool(self, embedder, index):
        binding = RecordingBinding()
        service = ToolRegistryService(embedder=embedder, index=index)
        service.publish(
            GITHUB, [_tool(GITHUB, "create_issue", "Create an issue.", binding=binding)]
        )
        service.search_tools("open a ticket")
        assert binding.calls == []

    def test_search_reports_tools_that_still_need_configuration(self, embedder, index):
        service = ToolRegistryService(embedder=embedder, index=index)
        service.publish(
            GITHUB,
            [
                _tool(
                    GITHUB,
                    "create_issue",
                    "Create an issue.",
                    requirements=ToolRequirements(
                        config=(ConfigRequirement(key="access_token", secret=True),)
                    ),
                )
            ],
        )
        (result,) = service.search_tools("open a ticket")
        assert result.availability.available is False
        assert result.availability.missing_config == ("access_token",)


# --------------------------------------------------------------------------- #
# Index lifecycle                                                              #
# --------------------------------------------------------------------------- #


class TestIndexLifecycle:
    def test_publication_is_lazy_and_the_first_search_indexes(
        self, registry, embedder, index
    ):
        assert embedder.embedded == []
        registry.search_tools("open a ticket")
        assert len(embedder.embedded) == 5
        assert index.size() == 5

    def test_unchanged_definitions_are_not_re_embedded(self, registry, embedder):
        assert registry.sync_index() == 5
        assert registry.sync_index() == 0
        registry.search_tools("open a ticket")
        assert len(embedder.embedded) == 5

    def test_searches_without_changes_skip_fingerprinting(self, registry, monkeypatch):
        registry.sync_index()
        calls = []
        original = ToolRegistryService._fingerprint
        monkeypatch.setattr(
            ToolRegistryService,
            "_fingerprint",
            staticmethod(lambda d, k: calls.append(d) or original(d, k)),
        )
        registry.search_tools("open a ticket")
        assert calls == []
        registry.publish(MAIL, _catalog()[MAIL])
        registry.search_tools("open a ticket")
        assert len(calls) == 5

    def test_a_changed_definition_is_re_embedded_alone(self, registry, embedder):
        registry.sync_index()
        embedder.embedded.clear()
        registry.publish(
            MAIL,
            [_tool(MAIL, "send_email", "Send an email message to a recipient, fast.")],
        )
        assert registry.sync_index() == 1
        assert embedder.embedded == [
            registry.get_definition(f"{MAIL}/send_email").embedding_text()
        ]

    def test_republishing_an_identical_module_embeds_nothing(self, registry):
        registry.sync_index()
        registry.publish(MAIL, _catalog()[MAIL])
        assert registry.sync_index() == 0

    def test_removed_definitions_leave_the_index(self, registry, index):
        registry.sync_index()
        registry.unpublish(WEATHER)
        registry.sync_index()
        assert index.size() == 4
        names = [r.name for r in registry.search_tools("weather forecast", limit=5)]
        assert "get_forecast" not in names

    def test_an_embedding_model_change_re_embeds_everything(
        self, registry, embedder, index
    ):
        registry.sync_index()
        embedder.key = "fixture/concepts-v2"
        embedder.embedded.clear()
        assert registry.sync_index() == 5
        assert index.size() == 5

    def test_stale_index_entries_from_a_previous_process_are_ignored(
        self, embedder, index
    ):
        from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
            concept_vector,
        )
        from naas_abi_core.services.tool_registry.ToolRegistryPort import (
            ToolIndexEntry,
        )

        index.prepare(embedder.model_key)
        index.upsert(
            [
                ToolIndexEntry(
                    id=f"{GITHUB}/deleted_tool@1",
                    fingerprint="old",
                    vector=tuple(concept_vector("open a ticket")),
                )
            ]
        )
        service = ToolRegistryService(embedder=embedder, index=index)
        service.publish(MAIL, _catalog()[MAIL])

        results = service.search_tools("open a ticket", limit=5)

        assert [r.name for r in results] == ["send_email"]
        assert index.fingerprints([f"{GITHUB}/deleted_tool@1"]) == {}

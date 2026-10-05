from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphQuerySpecError
from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (  # noqa: E501
    GraphQueryTripleStoreAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.adapters.secondary.memory import (
    InMemorySearchTopicStore,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.builtin import BUILTIN_TOPICS
from naas_abi.apps.nexus.apps.api.app.services.search.topics.service import SearchTopicService
from naas_abi.apps.nexus.apps.api.app.services.search.topics.templating import (
    render,
    validate_query,
    validate_topic,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import (
    SearchTopic,
    SearchTopicNotFoundError,
    SearchTopicValidationError,
    TopicResultRowDef,
)
from rdflib import Graph

WS = "ws-1"
DEMO_TTL = next(
    (
        parent
        / "libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/graphs/demo/personnel.ttl"
        for parent in Path(__file__).resolve().parents
        if (
            parent
            / "libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/graphs/demo/personnel.ttl"
        ).exists()
    ),
    None,
)
ALICE = "http://ontology.naas.ai/abi/Person/alice-dupont"


@pytest.fixture(scope="module")
def store() -> GraphQueryTripleStoreAdapter:
    if DEMO_TTL is None:
        pytest.skip("personnel demo graph (people + personnel records) not available")
    return GraphQueryTripleStoreAdapter(Graph().parse(DEMO_TTL, format="turtle"))


@pytest.fixture
def service() -> SearchTopicService:
    return SearchTopicService(InMemorySearchTopicStore())


class TestContract:
    @pytest.mark.parametrize("topic_id", sorted(BUILTIN_TOPICS))
    def test_builtin_topics_fit_their_contract(self, topic_id: str) -> None:
        validate_topic(BUILTIN_TOPICS[topic_id])

    def test_results_query_must_project_uri_and_title(self) -> None:
        errors = validate_query("SELECT ?uri WHERE { ?uri ?p ?o }", "results")
        assert errors == ["must project ?title"]

    def test_placeholder_outside_role_is_rejected(self) -> None:
        errors = validate_query(
            'SELECT ?title WHERE { {{ uri }} ?p ?title FILTER(?title = "{{ q }}") }', "header"
        )
        assert any("{{ q }}" in e for e in errors)

    def test_updates_are_rejected(self) -> None:
        assert validate_query("INSERT DATA { <a:a> <a:b> <a:c> }", "results")

    def test_federation_and_datasets_are_rejected(self) -> None:
        query = "SELECT ?uri ?title FROM <http://other/graph> WHERE { ?uri ?p ?title }"
        assert "not allowed" in validate_query(query, "results")[0]

    def test_search_text_cannot_escape_its_literal(self) -> None:
        rendered = render(
            'SELECT ?uri ?title WHERE { ?uri ?p ?title FILTER(CONTAINS(?title, "{{ q }}")) }',
            "results",
            {"q": '") } DROP ALL #', "limit": 1, "offset": 0},
        )
        assert '"\\") } DROP ALL #"' in rendered

    def test_uri_is_validated(self) -> None:
        with pytest.raises(GraphQuerySpecError):
            render("SELECT ?title WHERE { {{ uri }} ?p ?title }", "header", {"uri": "x> } ; <y"})


class TestDefinitions:
    async def test_lists_builtins_by_order(self, service: SearchTopicService) -> None:
        assert [t.id for t in await service.list_topics(WS)] == ["person", "organization"]

    async def test_override_then_reset(self, service: SearchTopicService) -> None:
        renamed = replace(BUILTIN_TOPICS["person"], label="Consultant")
        saved = await service.save_topic(WS, renamed, user_id="u")
        assert saved.source == "override"
        assert (await service.get_topic(WS, "person")).label == "Consultant"
        assert (await service.get_topic("other-ws", "person")).label == "Person"
        assert (await service.reset_topic(WS, "person")).label == "Person"  # type: ignore[union-attr]

    async def test_custom_topic_is_validated(self, service: SearchTopicService) -> None:
        broken = SearchTopic.from_dict(
            {
                "id": "skill",
                "label": "Skill",
                "results_query": "SELECT ?uri WHERE { ?uri ?p ?o }",
                "header_query": "SELECT ?title WHERE { {{ uri }} ?p ?title }",
            }
        )
        with pytest.raises(SearchTopicValidationError) as exc:
            await service.save_topic(WS, broken, user_id="u")
        assert exc.value.errors == ["results query: must project ?title"]

    async def test_topic_cannot_shadow_a_feature_scope(self, service: SearchTopicService) -> None:
        shadow = replace(BUILTIN_TOPICS["person"], id="files")
        with pytest.raises(SearchTopicValidationError) as exc:
            await service.save_topic(WS, shadow, user_id="u")
        assert exc.value.errors == ["id 'files' is reserved for a search scope"]

    async def test_reset_unknown_custom_topic(self, service: SearchTopicService) -> None:
        with pytest.raises(SearchTopicNotFoundError):
            await service.reset_topic(WS, "nope")

    def test_round_trips_through_dict(self) -> None:
        topic = BUILTIN_TOPICS["person"]
        assert SearchTopic.from_dict(topic.to_dict()) == topic


class TestExecution:
    async def test_empty_query_lists_every_person(self, service: SearchTopicService, store) -> None:
        results = await service.search(WS, "person", "", store)
        assert len(results.items) == 8
        assert all(item.uri.startswith("http") for item in results.items)

    async def test_matches_name_case_insensitively(
        self, service: SearchTopicService, store
    ) -> None:
        results = await service.search(WS, "person", "ALICE", store)
        assert [i.uri for i in results.items] == [ALICE]

    async def test_has_more_pages(self, service: SearchTopicService, store) -> None:
        page = await service.search(WS, "person", "", store, limit=3)
        assert len(page.items) == 3 and page.has_more

    async def test_person_detail_has_sections(self, service: SearchTopicService, store) -> None:
        detail = await service.detail(WS, "person", ALICE, store)
        assert detail.title
        sections = {s.id: s for s in detail.sections}
        assert set(sections) == {"experience", "education", "skills", "languages"}
        assert sections["experience"].items and not sections["experience"].error
        assert any(i.item for i in sections["experience"].items)

    async def test_experience_shows_the_skills_it_developed(
        self, service: SearchTopicService, store
    ) -> None:
        detail = await service.detail(WS, "person", ALICE, store)
        experience = next(s for s in detail.sections if s.id == "experience")
        tags = [tag for item in experience.items for tag in item.tags]
        assert "Python" in tags
        assert all(len(item.tags) == len(set(item.tags)) for item in experience.items)

    async def test_organization_links_back_to_people(
        self, service: SearchTopicService, store
    ) -> None:
        orgs = await service.search(WS, "organization", "", store)
        assert orgs.items
        detail = await service.detail(WS, "organization", orgs.items[0].uri, store)
        people = next(s for s in detail.sections if s.id == "people")
        assert people.link_topic == "person" and people.items

    async def test_unknown_individual(self, service: SearchTopicService, store) -> None:
        with pytest.raises(SearchTopicNotFoundError):
            await service.detail(WS, "person", "http://example.org/nobody", store)


class TestResultDecoration:
    def test_uris_render_as_a_values_block(self) -> None:
        rendered = render(
            "SELECT ?uri ?image WHERE { VALUES ?uri { {{ uris }} } ?uri <http://x/img> ?image }",
            "image",
            {"uris": ["http://a/1", "http://a/2"]},
        )
        assert "VALUES ?uri { <http://a/1> <http://a/2> }" in rendered

    def test_uris_are_validated(self) -> None:
        with pytest.raises(GraphQuerySpecError):
            render(
                "SELECT ?uri ?value WHERE { VALUES ?uri { {{ uris }} } }",
                "row",
                {"uris": ["not an iri"]},
            )

    def test_row_query_must_project_uri_and_value(self) -> None:
        errors = validate_query("SELECT ?uri WHERE { VALUES ?uri { {{ uris }} } }", "row")
        assert errors == ["must project ?value"]

    def test_rows_round_trip_and_are_validated(self) -> None:
        person = BUILTIN_TOPICS["person"]
        assert SearchTopic.from_dict(person.to_dict()) == person
        broken = replace(person, image_query="SELECT ?uri WHERE { VALUES ?uri { {{ uris }} } }")
        with pytest.raises(SearchTopicValidationError, match="image query"):
            validate_topic(broken)

    async def test_people_get_portraits_and_rows(self, service: SearchTopicService, store) -> None:
        results = await service.search(WS, "person", "alice", store)
        alice = next(item for item in results.items if item.uri == ALICE)
        assert [row.id for row in alice.rows][:1] == ["organization"]
        assert all(row.value for row in alice.rows)

    async def test_organizations_count_people_in_a_row(
        self, service: SearchTopicService, store
    ) -> None:
        results = await service.search(WS, "organization", "", store)
        top = results.items[0]
        assert any(row.id == "people" and int(row.value) > 0 for row in top.rows)

    async def test_a_broken_row_leaves_the_results(
        self, service: SearchTopicService, store
    ) -> None:
        person = BUILTIN_TOPICS["person"]
        failing = replace(
            person.result_rows[0],
            query="SELECT ?uri ?value WHERE { VALUES ?uri { {{ uris }} } BIND(1/0 AS ?value) }",
        )
        await service.save_topic(WS, replace(person, result_rows=(failing,)), user_id="u")
        results = await service.search(WS, "person", "", store)
        assert results.items and all(not item.rows for item in results.items)


SERVICE_LINE = TopicResultRowDef(
    id="service_line",
    label="Service line",
    query="""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX abi: <http://ontology.naas.ai/abi/>
SELECT ?uri ?value
WHERE {
  VALUES ?uri { {{ uris }} }
  ?line rdf:type abi:ServiceLine ; abi:hasMemberPart ?uri ; rdfs:label ?value .
}""",
)
GRADE = TopicResultRowDef(
    id="grade",
    label="Grade",
    query="""PREFIX abi: <http://ontology.naas.ai/abi/>
SELECT ?uri ?value
WHERE {
  VALUES ?uri { {{ uris }} }
  ?uri abi:hasGrade ?grade .
  ?grade abi:grade_value ?value .
}""",
)


class TestDetailFacts:
    def test_header_is_employer_then_years_of_experience(self) -> None:
        person = BUILTIN_TOPICS["person"]
        assert "?employer ?yearsOfExperience" in person.header_query
        assert "hasGrade" not in person.header_query and "ServiceLine" not in person.header_query
        assert person.detail_facts == ()

    def test_facts_round_trip_and_are_validated(self) -> None:
        person = replace(BUILTIN_TOPICS["person"], detail_facts=(SERVICE_LINE, GRADE))
        assert SearchTopic.from_dict(person.to_dict()) == person
        validate_topic(person)
        with pytest.raises(SearchTopicValidationError, match="detail fact grade"):
            validate_topic(replace(person, detail_facts=(replace(GRADE, label=""),)))

    async def test_organization_header_is_people_then_consultants(
        self, service: SearchTopicService, store
    ) -> None:
        org = BUILTIN_TOPICS["organization"]
        assert org.detail_label == "Profile"
        assert "?consultants" not in org.header_query
        assert [fact.id for fact in org.detail_facts] == ["consultants"]
        orgs = await service.search(WS, "organization", "", store)
        detail = await service.detail(WS, "organization", orgs.items[0].uri, store)
        keys = [fact.key for fact in detail.facts]
        assert keys[0] == "people"
        assert "consultants" not in keys or keys.index("consultants") == len(keys) - 1

    async def test_configured_facts_follow_the_header_facts(
        self, service: SearchTopicService, store
    ) -> None:
        person = BUILTIN_TOPICS["person"]
        await service.save_topic(
            WS, replace(person, detail_facts=(SERVICE_LINE, GRADE)), user_id="u"
        )
        detail = await service.detail(WS, "person", ALICE, store)
        keys = [fact.key for fact in detail.facts]
        assert keys[-2:] == ["service_line", "grade"]
        assert keys.index("employer") < keys.index("service_line")
        assert next(f for f in detail.facts if f.key == "grade").value == "Partner"

    async def test_a_broken_fact_is_left_out(self, service: SearchTopicService, store) -> None:
        broken = replace(
            GRADE,
            query="SELECT ?uri ?value WHERE { VALUES ?uri { {{ uris }} } BIND(1/0 AS ?value) }",
        )
        await service.save_topic(
            WS, replace(BUILTIN_TOPICS["person"], detail_facts=(broken,)), user_id="u"
        )
        detail = await service.detail(WS, "person", ALICE, store)
        assert detail.title and all(fact.key != "grade" for fact in detail.facts)


class TestGraphScope:
    def test_no_graphs_means_every_workspace_graph(self) -> None:
        from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
        from naas_abi.apps.nexus.apps.api.app.services.search.topics.scope import topic_scope

        scope = GraphAccessScope("w", frozenset({"urn:a", "urn:b"}), frozenset({"urn:a"}))
        narrowed = topic_scope(scope, ())
        assert narrowed.readable == {"urn:a", "urn:b"} and not narrowed.writable

    def test_named_graphs_never_widen_access(self) -> None:
        from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
        from naas_abi.apps.nexus.apps.api.app.services.search.topics.scope import topic_scope

        scope = GraphAccessScope("w", frozenset({"urn:a", "urn:b"}), frozenset())
        assert topic_scope(scope, ("urn:b", "urn:secret")).readable == {"urn:b"}

    def test_graphs_round_trip_and_are_validated(self) -> None:
        topic = replace(BUILTIN_TOPICS["person"], graphs=("http://x/g",))
        assert SearchTopic.from_dict(topic.to_dict()).graphs == ("http://x/g",)
        with pytest.raises(SearchTopicValidationError):
            validate_topic(replace(topic, graphs=("not an iri>",)))


class TestScopeSwitches:
    async def test_defaults_keep_apps_chats_agents_and_web(
        self, service: SearchTopicService
    ) -> None:
        disabled = await service.disabled_scopes(WS)
        assert not disabled & {"apps", "chat", "agents", "web.wikipedia", "web.duckduckgo"}
        assert disabled == {
            "files",
            "documents",
            "slides",
            "sheets",
            "datasets",
            "ontology",
            "graph",
            "maps",
        }

    async def test_switch_off_and_on_per_workspace(self, service: SearchTopicService) -> None:
        await service.set_scope_enabled(WS, "files", True, user_id="u")
        await service.set_scope_enabled(WS, "web.wikipedia", False, user_id="u")
        disabled = await service.disabled_scopes(WS)
        assert "files" not in disabled and "web.wikipedia" in disabled
        assert "files" in await service.disabled_scopes("other-ws")
        await service.set_scope_enabled(WS, "apps", False, user_id="u")
        assert "apps" in await service.disabled_scopes(WS)

    async def test_topics_are_not_switched_here(self, service: SearchTopicService) -> None:
        with pytest.raises(SearchTopicNotFoundError):
            await service.set_scope_enabled(WS, "person", False, user_id="u")

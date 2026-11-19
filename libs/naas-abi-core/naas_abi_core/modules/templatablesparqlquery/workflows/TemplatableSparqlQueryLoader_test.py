"""Templatable queries come from the engine's own module files only."""

from __future__ import annotations

from types import SimpleNamespace

from naas_abi_core.modules.templatablesparqlquery.workflows.TemplatableSparqlQueryLoader import (
    TemplatableSparqlQueryLoader,
    first_party_ontologies,
)

QUERIES = """@prefix intentMapping: <http://ontology.naas.ai/intentMapping/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/> .

ex:findThing a intentMapping:TemplatableSparqlQuery ;
    rdfs:label "find_thing" ;
    intentMapping:intentDescription "Find a thing by label" ;
    intentMapping:sparqlTemplate "SELECT ?s WHERE { ?s ?p '{{ label }}' }" ;
    intentMapping:hasArgument ex:labelArgument .

ex:labelArgument a intentMapping:QueryArgument ;
    intentMapping:argumentName "label" ;
    intentMapping:argumentDescription "A label" ;
    intentMapping:validationPattern ".*" ;
    intentMapping:validationFormat "text" .
"""


class _SharedGraph:
    """A triple store whose schema graph holds a query loaded by someone else."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def query(self, sparql: str) -> list:
        self.queries.append(sparql)
        return []


def test_templatable_queries_keep_to_first_party_files(tmp_path):
    ontology = tmp_path / "FirstPartyQueries.ttl"
    ontology.write_text(QUERIES)
    store = _SharedGraph()

    workflows = TemplatableSparqlQueryLoader(
        store,  # type: ignore[arg-type]
        [str(ontology)],
    ).load_workflows()

    assert [w.name for w in workflows] == ["find_thing"]
    assert store.queries == []  # the shared schema graph is never read
    workflows[0].run(workflows[0].arguments_model(label="a"))
    assert store.queries == ["SELECT ?s WHERE { ?s ?p 'a' }"]


def test_templatable_queries_keep_out_of_an_empty_engine():
    store = _SharedGraph()

    assert TemplatableSparqlQueryLoader(store).load_workflows() == []  # type: ignore[arg-type]
    assert store.queries == []


def test_first_party_ontologies_are_the_engine_modules_files():
    modules = [
        SimpleNamespace(ontologies=["/a/One.ttl", "/a/Two.ttl"]),
        SimpleNamespace(ontologies=[]),
        object(),
    ]

    assert first_party_ontologies(modules) == ["/a/One.ttl", "/a/Two.ttl"]


def test_shipped_iri_arguments_keep_inside_their_iri():
    from pathlib import Path

    import pytest
    from pydantic import ValidationError

    libs = Path(__file__).resolve().parents[5]
    files = [
        p
        for p in libs.glob("naas-abi*/naas_abi*/**/ontologies/**/*SparqlQuer*.ttl")
        if ".venv" not in p.parts and "templates" not in p.parts
    ]
    loader = TemplatableSparqlQueryLoader(_SharedGraph(), [str(p) for p in files])  # type: ignore[arg-type]
    checked = 0
    for workflow in loader.load_workflows():
        for name, field in workflow.arguments_model.model_fields.items():
            pattern = next(
                (getattr(m, "pattern", None) for m in field.metadata if getattr(m, "pattern", None)),
                None,
            )
            if not pattern or "http" not in pattern:
                continue
            checked += 1
            closing = "http://ontology.naas.ai/x> <y/00000000-0000-0000-0000-000000000000"
            with pytest.raises(ValidationError) as refused:
                workflow.arguments_model(**{name: closing})
            assert any(
                e["loc"] == (name,) and e["type"] == "string_pattern_mismatch"
                for e in refused.value.errors()
            )
            valid = "http://ontology.naas.ai/x/00000000-0000-0000-0000-000000000000"
            try:
                workflow.arguments_model(**{name: valid})
            except ValidationError as exc:
                assert all(e["loc"] != (name,) for e in exc.errors())
    assert checked > 0

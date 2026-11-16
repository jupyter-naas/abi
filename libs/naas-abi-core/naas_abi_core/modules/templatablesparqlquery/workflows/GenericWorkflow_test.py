import pytest
from naas_abi_core.modules.templatablesparqlquery.workflows.GenericWorkflow import (
    GenericWorkflow,
)
from pydantic import BaseModel


class _Arguments(BaseModel):
    name: str


class _Store:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def query(self, sparql: str) -> list:
        self.queries.append(sparql)
        return []


def test_the_rendered_query_is_not_printed(capsys):
    store = _Store()
    workflow = GenericWorkflow(
        name="find",
        description="",
        sparql_template='SELECT ?s WHERE { ?s rdfs:label "{{ name }}" }',
        arguments_model=_Arguments,
        triple_store_service=store,  # type: ignore[arg-type]
    )

    workflow.run(_Arguments(name="a private name"))

    assert store.queries == ['SELECT ?s WHERE { ?s rdfs:label "a private name" }']
    captured = capsys.readouterr()
    assert "a private name" not in captured.out + captured.err


class _GraphStore:
    """A real rdflib graph: the rendered query runs, so a breakout would show."""

    def __init__(self) -> None:
        from rdflib import Graph, Literal, Namespace
        from rdflib.namespace import RDFS

        ex = Namespace("http://example.org/")
        self.graph = Graph()
        self.graph.add((ex.a, RDFS.label, Literal("Alpha")))
        self.graph.add((ex.b, RDFS.label, Literal('Say "hi"')))
        self.graph.add((ex.secret, RDFS.label, Literal("Secret")))

    def query(self, sparql: str):
        return self.graph.query(sparql)


def _workflow(template: str, arguments: type[BaseModel]) -> GenericWorkflow:
    return GenericWorkflow(
        name="find",
        description="",
        sparql_template=template,
        arguments_model=arguments,
        triple_store_service=_GraphStore(),  # type: ignore[arg-type]
    )


LABEL_SEARCH = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?s WHERE { ?s rdfs:label ?l .
  FILTER(CONTAINS(LCASE(STR(?l)), LCASE("{{ name }}"))) }"""


def test_a_literal_argument_cannot_add_patterns():
    workflow = _workflow(LABEL_SEARCH, _Arguments)

    # Unescaped, this closed the literal and matched every triple.
    assert workflow.run(_Arguments(name='a")) } UNION { ?s ?p ?o } #')) is None
    assert workflow.run(_Arguments(name='say "hi')) == [{"s": "http://example.org/b"}]


class _UriArguments(BaseModel):
    uri: str


def test_an_iri_argument_that_leaves_its_iri_is_an_error():
    workflow = _workflow(
        """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?l WHERE { <{{ uri }}> rdfs:label ?l }""",
        _UriArguments,
    )

    assert workflow.run(_UriArguments(uri="http://example.org/a")) == [{"l": "Alpha"}]
    result = workflow.run(
        _UriArguments(uri="http://example.org/a> rdfs:label ?l } UNION { ?s ?p ?l } #")
    )
    assert "not a valid IRI" in result[0]["error"]


def _run(template: str, name: str) -> tuple[list, list[str]]:
    store = _Store()
    workflow = GenericWorkflow(
        name="find",
        description="",
        sparql_template=template,
        arguments_model=_Arguments,
        triple_store_service=store,  # type: ignore[arg-type]
    )
    return workflow.run(_Arguments(name=name)), store.queries


@pytest.mark.parametrize(
    "template",
    [
        "{{ cycler.__init__.__globals__.os.getcwd() }}",
        "{{ ''.__class__.__mro__[1].__subclasses__() }}",
        "{{ lipsum.__globals__['os'].getcwd() }}",
        "{{ name.__class__.__init__.__globals__ }}",
    ],
)
def test_templatable_query_keeps_templates_sandboxed(template):
    result, queries = _run(template, "x")

    assert queries == []
    assert "error" in result[0]


def test_templatable_query_keeps_arguments_inside_their_literal():
    _, queries = _run(
        'SELECT ?s WHERE { ?s rdfs:label "{{ name }}" }',
        'x" } ; DROP ALL ; #\\\n',
    )

    assert queries == [
        'SELECT ?s WHERE { ?s rdfs:label "x\\" } ; DROP ALL ; #\\\\\\n" }'
    ]

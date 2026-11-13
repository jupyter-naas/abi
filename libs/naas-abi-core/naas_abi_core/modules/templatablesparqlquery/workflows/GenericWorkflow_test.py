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

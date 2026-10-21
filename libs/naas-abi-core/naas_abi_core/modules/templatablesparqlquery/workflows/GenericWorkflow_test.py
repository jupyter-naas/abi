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

"""Templatable SPARQL queries as agent tools, without core.

The in-engine modules got these tools from ``naas_abi_core.modules.
templatablesparqlquery``, which read ``intentMapping:TemplatableSparqlQuery``
individuals from the engine's schema graph. A remote module reads them from
its own ``ontologies/*.ttl`` files instead (the same files it sends to the
schema graph) and runs the rendered query on the engine's triple store.

Same tool names, descriptions and argument validation (``validationPattern``).
A query without arguments is loaded too (core's loader required one).
Needs ``jinja2`` and ``naas-abi-sdk[rdf]``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import RDF, RDFS, Graph, Namespace

IM = Namespace("http://ontology.naas.ai/intentMapping/")


@dataclass(frozen=True)
class Argument:
    name: str
    description: str
    pattern: str | None
    example: str | None


@dataclass(frozen=True)
class TemplatableQuery:
    name: str
    description: str
    template: str
    arguments: tuple[Argument, ...]


def _text(graph: Graph, subject: Any, predicate: Any) -> str | None:
    value = graph.value(subject, predicate)
    return None if value is None else str(value)


def load_queries(paths: Iterable[Path]) -> list[TemplatableQuery]:
    """Every templatable query defined in the given Turtle files."""
    graph = Graph()
    for path in paths:
        graph.parse(path, format="turtle")
    queries = []
    for subject in graph.subjects(RDF.type, IM.TemplatableSparqlQuery):
        arguments = tuple(
            sorted(
                (
                    Argument(
                        name=_text(graph, argument, IM.argumentName) or "",
                        description=_text(graph, argument, IM.argumentDescription)
                        or "",
                        pattern=_text(graph, argument, IM.validationPattern),
                        example=_text(graph, argument, IM.validationFormat),
                    )
                    for argument in graph.objects(subject, IM.hasArgument)
                ),
                key=lambda a: a.name,
            )
        )
        queries.append(
            TemplatableQuery(
                name=_text(graph, subject, RDFS.label) or "",
                description=_text(graph, subject, IM.intentDescription) or "",
                template=_text(graph, subject, IM.sparqlTemplate) or "",
                arguments=arguments,
            )
        )
    return sorted(queries, key=lambda q: q.name)


def results_to_list(result: Any) -> list[dict[str, str | None]] | None:
    """As core's ``SPARQLUtils.results_to_list``: rows by variable, None when empty."""
    data = []
    for row in result:
        values = row.asdict() if hasattr(row, "asdict") else {}
        labels = getattr(row, "labels", None) or values
        data.append(
            {str(k): (str(values[k]) if values.get(k) else None) for k in labels}
        )
    return data or None


def query_tools(
    queries: Iterable[TemplatableQuery],
    triple_store: Any,
    names: Iterable[str] | None = None,
) -> list[Any]:
    """One LangChain tool per query (``names``: only those)."""
    from jinja2 import Template
    from langchain_core.tools import StructuredTool
    from pydantic import Field, create_model

    wanted = set(names) if names is not None else None
    tools = []
    for query in queries:
        if wanted is not None and query.name not in wanted:
            continue
        model = create_model(
            f"{query.name.capitalize()}Arguments",
            **{
                a.name: (
                    str,
                    Field(
                        ...,
                        description=a.description,
                        pattern=a.pattern,
                        json_schema_extra={"example": a.example} if a.example else None,
                    ),
                )
                for a in query.arguments
            },
        )
        template = Template(query.template)

        def make(template: Template = template, model: type = model) -> Any:
            async def run(**arguments: Any) -> Any:
                try:
                    values = model(**arguments).model_dump()
                    return results_to_list(
                        await triple_store.query(template.render(**values))
                    )
                except Exception as exc:  # noqa: BLE001 - reported to the agent, as in core
                    return [{"error": str(exc)}]

            return run

        tools.append(
            StructuredTool(
                name=query.name,
                description=query.description,
                coroutine=make(),
                args_schema=model,
            )
        )
    return tools


def module_queries(package_dir: Path) -> list[TemplatableQuery]:
    """The templatable queries of a module's ``ontologies/`` folder."""
    return load_queries(sorted((package_dir / "ontologies").rglob("*.ttl")))

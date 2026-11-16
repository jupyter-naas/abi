"""Templatable SPARQL queries as agent tools, without core.

The in-engine modules got these tools from ``naas_abi_core.modules.
templatablesparqlquery``, which read ``intentMapping:TemplatableSparqlQuery``
individuals from the engine's schema graph. A remote module reads them from
its own ``ontologies/*.ttl`` files instead (the same files it sends to the
schema graph) and runs the rendered query on the engine's triple store.

Same tool names, descriptions and argument validation (``validationPattern``).
A query without arguments is loaded too (core's loader required one).
Needs ``jinja2`` and ``naas-abi-sdk[rdf]``.

Unlike core, an argument cannot change the query: where its placeholder
stands decides how it is rendered (``placeholder_contexts``). Inside a string
literal it is escaped; inside ``<...>`` it must be IRI characters; anywhere
else it must be a number. A value that does not fit is an error, not a query.
A ``validationPattern`` such as ``"."`` was the only guard before.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import RDF, RDFS, Graph, Namespace

IM = Namespace("http://ontology.naas.ai/intentMapping/")

STRING, IRI, BARE = "string", "iri", "bare"
_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)[^}]*\}\}")
# IRIREF excludes these (SPARQL 1.1 grammar, [139]).
_NOT_IRI = re.compile(r'[\x00-\x20<>"{}|^`\\]')
_NUMBER = re.compile(r"[+-]?\d+(\.\d+)?")


def _in_string(text: str) -> bool:
    """Whether ``text`` ends inside a quoted SPARQL literal (comments and
    escapes skipped; a long literal counts as three quotes, the same parity)."""
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#":
            newline = text.find("\n", index)
            if newline == -1:
                return False
            index = newline
        index += 1
    return quote is not None


def _in_iri(before: str, after: str) -> bool:
    """Whether the placeholder sits inside ``<...>`` (no space between)."""
    head = re.search(r"[<>\s]", before[::-1])
    tail = re.search(r"[<>\s]", after)
    return (
        head is not None
        and head.group() == "<"
        and tail is not None
        and tail.group() == ">"
    )


def placeholder_contexts(template: str) -> dict[str, set[str]]:
    """Argument name -> where its placeholders stand: STRING, IRI or BARE."""
    contexts: dict[str, set[str]] = {}
    for match in _PLACEHOLDER.finditer(template):
        before, after = template[: match.start()], template[match.end() :]
        if _in_string(before):
            context = STRING
        elif _in_iri(before, after):
            context = IRI
        else:
            context = BARE
        contexts.setdefault(match.group(1), set()).add(context)
    return contexts


def escape_literal(value: str) -> str:
    """``value`` as the inside of a quoted SPARQL literal (either quote)."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def safe_values(
    values: dict[str, Any], contexts: dict[str, set[str]]
) -> dict[str, Any]:
    """The values to render: escaped for a literal, checked for an IRI or a
    bare token. Raises ``ValueError`` for a value its place cannot hold."""
    rendered: dict[str, Any] = {}
    for name, value in values.items():
        text = "" if value is None else str(value)
        where = contexts.get(name, set())
        if IRI in where and _NOT_IRI.search(text):
            raise ValueError(f"{name}: not a valid IRI: {text!r}")
        if BARE in where and not _NUMBER.fullmatch(text):
            raise ValueError(f"{name}: must be a number, got {text!r}")
        rendered[name] = escape_literal(text) if STRING in where else text
    return rendered


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
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    from langchain_core.tools import StructuredTool
    from pydantic import Field, create_model

    wanted = set(names) if names is not None else None
    # Sandboxed: a template reaches its arguments, never Python objects.
    environment = ImmutableSandboxedEnvironment(autoescape=False)
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
        template = environment.from_string(query.template)
        contexts = placeholder_contexts(query.template)

        def make(
            template: Any = template,
            model: type = model,
            contexts: dict[str, set[str]] = contexts,
        ) -> Any:
            async def run(**arguments: Any) -> Any:
                try:
                    values = safe_values(model(**arguments).model_dump(), contexts)
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

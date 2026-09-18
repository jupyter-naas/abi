"""Competency SPARQL templates from PersonnelSparqlQueries.ttl.

Shared by the graph exporter and the profile API so the UI can show the same
queries that populate each section.
"""

from __future__ import annotations

import re
import textwrap
from functools import lru_cache
from typing import Any

from naas_abi_marketplace.domains.personnel.paths import ONTOLOGIES_DIR
from rdflib import RDF, RDFS, Graph, URIRef

INTENT = "http://ontology.naas.ai/intentMapping/"
GRAPH_IRI = "http://ontology.naas.ai/graph/personnel"
QUERIES_TTL = ONTOLOGIES_DIR / "queries" / "PersonnelSparqlQueries.ttl"
DEFAULT_ROW_LIMIT = 2000


@lru_cache(maxsize=1)
def _queries_graph() -> Graph:
    return Graph().parse(QUERIES_TTL, format="turtle")


@lru_cache(maxsize=1)
def load_queries() -> dict[str, str]:
    graph = _queries_graph()
    return {
        str(graph.value(subject, RDFS.label)): str(
            graph.value(subject, URIRef(INTENT + "sparqlTemplate"))
        )
        for subject in graph.subjects(
            RDF.type, URIRef(INTENT + "TemplatableSparqlQuery")
        )
    }


@lru_cache(maxsize=1)
def load_query_descriptions() -> dict[str, str]:
    graph = _queries_graph()
    intent_description = URIRef(INTENT + "intentDescription")
    descriptions: dict[str, str] = {}
    for subject in graph.subjects(
        RDF.type, URIRef(INTENT + "TemplatableSparqlQuery")
    ):
        name = str(graph.value(subject, RDFS.label))
        if not name:
            continue
        raw = graph.value(subject, intent_description)
        descriptions[name] = str(raw).strip() if raw else ""
    return descriptions


def format_query_label(query_name: str) -> str:
    """Turn ``find_active_employees`` into ``Find Active Employees``."""
    return " ".join(part.capitalize() for part in query_name.split("_") if part)


def human_query_title(query_name: str, *, max_len: int = 120) -> str:
    """Short label for UI lists, from the query intent description."""
    description = load_query_descriptions().get(query_name, "")
    if description:
        sentence = description.split(".")[0].strip()
        if len(sentence) > max_len:
            return sentence[: max_len - 3].rstrip() + "..."
        return sentence
    return query_name.replace("_", " ")


def format_sparql(sparql: str) -> str:
    """Pretty-print SPARQL for display (modal, docs). Does not change semantics."""
    lines = textwrap.dedent(sparql).strip().splitlines()
    formatted: list[str] = []
    depth = 0
    in_select = False
    last_line_depth = 0
    triple_predicate_depth: int | None = None
    _PREDICATE_START = ("rdfs:", "rdf:", "abi:", "personnel:")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted.append("")
            continue

        if stripped.startswith("}"):
            depth = max(0, depth - 1)

        upper = stripped.upper()
        if upper.startswith("PREFIX "):
            in_select = False
            line_depth = 0
        elif upper.startswith("SELECT "):
            in_select = True
            line_depth = 0
        elif upper.startswith("WHERE "):
            in_select = False
            line_depth = 0
        elif upper.startswith("LIMIT ") or upper.startswith("ORDER BY"):
            in_select = False
            line_depth = 0
        elif in_select and stripped.startswith("?"):
            line_depth = 1
        elif stripped.startswith("#"):
            line_depth = depth
        elif triple_predicate_depth is not None and stripped.startswith(_PREDICATE_START):
            line_depth = triple_predicate_depth
        elif formatted and formatted[-1].rstrip().endswith(";") and stripped.startswith(
            _PREDICATE_START
        ):
            triple_predicate_depth = last_line_depth + 1
            line_depth = triple_predicate_depth
        else:
            line_depth = depth
            if stripped.startswith("?"):
                triple_predicate_depth = None

        formatted.append(("  " * line_depth) + stripped)
        last_line_depth = line_depth

        if stripped.endswith("."):
            triple_predicate_depth = None

        opens = stripped.count("{")
        closes = stripped.count("}")
        if stripped.startswith("}"):
            closes = max(0, closes - 1)
        depth += opens - closes
        depth = max(0, depth)

    return "\n".join(formatted)


def strip_named_graph(sparql: str) -> str:
    """Run the same query against a file, where there is only one graph."""
    return re.sub(rf"GRAPH\s*<{re.escape(GRAPH_IRI)}>\s*\{{", "{", sparql)


def fill_template(template: str, **arguments: object) -> str:
    filled = template
    for name, value in arguments.items():
        filled = filled.replace(f"{{{{ {name} }}}}", str(value))
    return filled


def _sparql_string_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def restrict_to_profile_slug(sparql: str, slug: str) -> str:
    """Narrow a directory-wide competency query to one profile slug."""
    escaped = _sparql_string_literal(slug)
    injection = f"""
            FILTER EXISTS {{
              ?person personnel:profile_slug ?__profileSlug .
              FILTER(LCASE(STR(?__profileSlug)) = LCASE("{escaped}"))
            }}
"""
    for marker in ("        ORDER BY", "        LIMIT"):
        if marker in sparql:
            return sparql.replace(marker, injection + marker, 1)
    return sparql.rstrip() + injection


def render_query_raw(
    query_name: str,
    *,
    slug: str | None = None,
    limit: int = DEFAULT_ROW_LIMIT,
    strip_graph: bool = True,
) -> str:
    """Filled SPARQL string, without pretty-printing."""
    try:
        template = load_queries()[query_name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown SPARQL query {query_name!r}. "
            f"Known: {', '.join(sorted(load_queries()))}"
        ) from exc
    sparql = template
    if strip_graph:
        sparql = strip_named_graph(sparql)
    if query_name == "find_profile_header":
        if not slug:
            raise ValueError("find_profile_header requires slug")
        return fill_template(
            sparql, person_slug=_sparql_string_literal(slug)
        ).strip()
    sparql = fill_template(sparql, limit=limit)
    if slug:
        sparql = restrict_to_profile_slug(sparql, slug)
    return sparql.strip()


def render_query(
    query_name: str,
    *,
    slug: str | None = None,
    limit: int = DEFAULT_ROW_LIMIT,
    strip_graph: bool = True,
    display: bool = True,
) -> str:
    """Fill a template and optionally restrict it to one person."""
    raw = render_query_raw(
        query_name, slug=slug, limit=limit, strip_graph=strip_graph
    )
    return format_sparql(raw) if display else raw


def run_query(
    graph: Graph, template: str, **arguments: object
) -> list[dict[str, Any]]:
    """Execute one filled template against an rdflib graph (exporter)."""
    sparql = fill_template(strip_named_graph(template), **arguments)
    rows: list[dict[str, Any]] = []
    for row in graph.query(sparql):
        rows.append(
            {
                key: (None if value is None else str(value))
                for key, value in row.asdict().items()
            }
        )
    return rows

"""Serialize discovery preview triples with rdflib (grouped by subject URI in Turtle)."""

from __future__ import annotations

from typing import Literal as TypingLiteral

from rdflib import Graph, Literal as RdflibLiteral, URIRef

ExportFormat = TypingLiteral["nt", "ttl", "owl"]

_EXPORT_META: dict[ExportFormat, tuple[str, str]] = {
    "nt": ("triples.nt", "application/n-triples"),
    "ttl": ("triples.ttl", "text/turtle"),
    "owl": ("triples.owl", "application/rdf+xml"),
}

_RDF_SERIALIZE_FORMAT: dict[ExportFormat, str] = {
    "nt": "nt",
    "ttl": "turtle",
    "owl": "xml",
}


def build_graph_from_triple_rows(rows: list[dict]) -> Graph:
    """Build an rdflib Graph from flat {s, p, o, is_literal} rows."""
    graph = Graph()
    seen: set[tuple[str, str, str, bool]] = set()
    for row in rows:
        subject = str(row["s"])
        predicate = str(row["p"])
        obj_value = str(row["o"])
        is_literal = bool(row.get("is_literal", False))
        key = (subject, predicate, obj_value, is_literal)
        if key in seen:
            continue
        seen.add(key)
        subj = URIRef(subject)
        pred = URIRef(predicate)
        obj: URIRef | RdflibLiteral = (
            RdflibLiteral(obj_value) if is_literal else URIRef(obj_value)
        )
        graph.add((subj, pred, obj))
    return graph


def serialize_discovery_triples(
    rows: list[dict],
    fmt: ExportFormat,
) -> tuple[str, str, str]:
    """
    Parse rows into an rdflib graph and serialize.

    Turtle output groups triples by subject URI (rdflib default).
    Returns (content, filename, media_type).
    """
    graph = build_graph_from_triple_rows(rows)
    rdflib_format = _RDF_SERIALIZE_FORMAT[fmt]
    serialized = graph.serialize(format=rdflib_format)
    if isinstance(serialized, bytes):
        content = serialized.decode("utf-8")
    else:
        content = str(serialized)
    filename, media_type = _EXPORT_META[fmt]
    return content, filename, media_type

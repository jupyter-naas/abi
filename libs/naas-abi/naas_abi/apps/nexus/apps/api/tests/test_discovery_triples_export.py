"""Tests for discovery triple export via rdflib."""

import importlib.util
from pathlib import Path

_GRAPH_DIR = Path(__file__).resolve().parents[1] / "app" / "services" / "graph"
_spec = importlib.util.spec_from_file_location(
    "discovery_triples_export",
    _GRAPH_DIR / "discovery_triples_export.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build_graph_from_triple_rows = _mod.build_graph_from_triple_rows
serialize_discovery_triples = _mod.serialize_discovery_triples

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
OWL_NI = "http://www.w3.org/2002/07/owl#NamedIndividual"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"


def _sample_rows() -> list[dict]:
    return [
        {"s": "http://example.org/a", "p": RDF_TYPE, "o": OWL_NI, "is_literal": False},
        {"s": "http://example.org/a", "p": RDFS_LABEL, "o": "Alpha", "is_literal": True},
        {"s": "http://example.org/b", "p": RDF_TYPE, "o": OWL_NI, "is_literal": False},
        {"s": "http://example.org/b", "p": RDFS_LABEL, "o": "Beta", "is_literal": True},
    ]


def test_build_graph_deduplicates_rows() -> None:
    graph = build_graph_from_triple_rows(_sample_rows() + [_sample_rows()[0]])
    assert len(graph) == 4


def test_turtle_groups_by_subject_uri() -> None:
    content, filename, media_type = serialize_discovery_triples(_sample_rows(), "ttl")
    assert filename == "triples.ttl"
    assert media_type == "text/turtle"
    assert content.count("http://example.org/a") >= 1
    assert ";" in content


def test_nt_serializes_all_triples() -> None:
    content, _, _ = serialize_discovery_triples(_sample_rows(), "nt")
    assert content.count(" .") >= 4

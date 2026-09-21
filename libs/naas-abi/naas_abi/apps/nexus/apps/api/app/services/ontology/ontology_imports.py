"""Resolve local ontology imports strictly inside an admitted catalog snapshot."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

Snapshot = tuple[tuple[str, int, int], ...]
_ABI = "http://ontology.naas.ai/abi/"


def _snapshot(paths: list[str]) -> Snapshot:
    return tuple(
        sorted(
            (path, stat.st_mtime_ns, stat.st_size)
            for path in set(paths)
            for stat in [Path(path).stat()]
        )
    )


@lru_cache(maxsize=8)
def _catalog_graphs(snapshot: Snapshot) -> dict[str, Graph]:
    return {
        path: Graph().parse(
            path,
            format={".ttl": "turtle", ".nt": "nt", ".owl": "xml", ".rdf": "xml"}.get(
                Path(path).suffix.lower()
            ),
        )
        for path, _, _ in snapshot
    }


@lru_cache(maxsize=32)
def _resolve(root: str, snapshot: Snapshot, aliases: tuple[tuple[str, str], ...]) -> Graph:
    graphs = _catalog_graphs(snapshot)
    by_iri: dict[str, set[str]] = {}
    suffixes: dict[str, set[str]] = {}
    for path, graph in graphs.items():
        by_iri.setdefault(Path(path).resolve().as_uri(), set()).add(path)
        for subject in graph.subjects(RDF.type, OWL.Ontology):
            by_iri.setdefault(str(subject), set()).add(path)
            package = graph.value(subject, URIRef(_ABI + "pythonPackage"))
            resource = graph.value(subject, URIRef(_ABI + "ontologyResource"))
            if package and resource:
                suffixes.setdefault(f"{package}/{resource}", set()).add(path)
        for uri, relative in aliases:
            if Path(path).name == Path(relative).name:
                by_iri.setdefault(uri, set()).add(path)

    result = Graph()
    pending = [root]
    visited: set[str] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        source = graphs[path]
        result += source
        for prefix, namespace in source.namespaces():
            result.bind(prefix, namespace)
        for imported in source.objects(None, OWL.imports):
            uri = str(imported)
            targets = set(by_iri.get(uri, ()))
            if uri.startswith("file://"):
                imported_path = unquote(urlparse(uri).path)
                for suffix, candidates in suffixes.items():
                    if imported_path.endswith("/" + suffix):
                        targets.update(candidates)
            # An unresolved import stays a reference. Never fetch or consult a global map.
            pending.extend(sorted(targets - visited))
    return result


def load_catalog_import_graph(root: str, paths: list[str], aliases: dict[str, str]) -> Graph:
    if root not in paths:
        raise ValueError("Ontology is outside the admitted catalog")
    return _resolve(root, _snapshot(paths), tuple(sorted(aliases.items())))


def clear_catalog_import_caches() -> None:
    _resolve.cache_clear()
    _catalog_graphs.cache_clear()

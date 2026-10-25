"""Resolve local ontology imports strictly inside an admitted catalog snapshot."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology_source import (
    active_reader,
    content_version,
    is_remote_id,
    load_remote_graph,
)
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

Snapshot = tuple[tuple[str, int, int], ...]
_ABI = "http://ontology.naas.ai/abi/"


def _version(path: str) -> tuple[int, int]:
    """A change token: a file's mtime and size, or a remote text's hash and length."""
    if is_remote_id(path):
        return content_version(active_reader().read(path))
    stat = Path(path).stat()
    return stat.st_mtime_ns, stat.st_size


def _snapshot(paths: list[str]) -> Snapshot:
    return tuple(sorted((path, *_version(path)) for path in set(paths)))


_FORMATS = {".ttl": "turtle", ".nt": "nt", ".owl": "xml", ".rdf": "xml"}


def _parse(path: str) -> Graph:
    if is_remote_id(path):
        return load_remote_graph(path)
    return Graph().parse(path, format=_FORMATS.get(Path(path).suffix.lower()))


@lru_cache(maxsize=8)
def _catalog_graphs(snapshot: Snapshot) -> dict[str, Graph]:
    return {path: _parse(path) for path, _, _ in snapshot}


@lru_cache(maxsize=64)
def _bundled_graph(path: str, mtime_ns: int) -> Graph:
    return Graph().parse(path, format=_FORMATS.get(Path(path).suffix.lower()))


@lru_cache(maxsize=32)
def _resolve(
    root: str,
    snapshot: Snapshot,
    aliases: tuple[tuple[str, str], ...],
    bundled_dir: str | None = None,
) -> Graph:
    graphs = dict(_catalog_graphs(snapshot))
    by_iri: dict[str, set[str]] = {}
    suffixes: dict[str, set[str]] = {}
    for path, graph in graphs.items():
        if not is_remote_id(path):
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
    # Standard upper ontologies (BFO, CCO) ship with the package rather than in
    # any workspace catalog. Only explicitly aliased IRIs may reach them, and
    # only when no catalog file already answers for that IRI.
    if bundled_dir:
        for uri, relative in aliases:
            bundled = Path(bundled_dir) / relative
            if uri not in by_iri and bundled.is_file():
                by_iri[uri] = {str(bundled)}

    result = Graph()
    pending = [root]
    visited: set[str] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        if path not in graphs:
            graphs[path] = _bundled_graph(path, Path(path).stat().st_mtime_ns)
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


def load_catalog_import_graph(
    root: str,
    paths: list[str],
    aliases: dict[str, str],
    bundled_dir: str | None = None,
) -> Graph:
    """Graph of ``root`` plus its transitive imports within the catalog.

    ``bundled_dir`` holds the package's own copies of the aliased standard
    ontologies; an aliased import with no catalog match is read from there.
    """
    if root not in paths:
        raise ValueError("Ontology is outside the admitted catalog")
    return _resolve(root, _snapshot(paths), tuple(sorted(aliases.items())), bundled_dir)


def clear_catalog_import_caches() -> None:
    _resolve.cache_clear()
    _catalog_graphs.cache_clear()
    _bundled_graph.cache_clear()

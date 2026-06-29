from __future__ import annotations

import os
import re
import shutil
import traceback
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
    OntologyFileItemData,
    OntologyItemData,
    OntologyOverviewAggregateStatsData,
    OntologyOverviewGraphData,
    OntologyOverviewGraphEdgeData,
    OntologyOverviewGraphNodeData,
    OntologyOverviewStatsData,
    OntologyParseError,
    OntologyPathNotFoundError,
    OntologyServiceUnavailableError,
    OntologyTypeCountsData,
    ReferenceClassData,
    ReferenceOntologyData,
    ReferencePropertyData,
)
from naas_abi_core import logger
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS
from rdflib.query import ResultRow
from rdflib.term import URIRef

_cache = CacheFactory.CacheFS_find_storage(subpath="nexus/ontology")

# In-memory cache for graphs loaded with owl:imports resolved (avoids re-fetching remote ontologies)
_graph_with_imports_cache: dict[str, Graph] = {}


def clear_graph_caches() -> None:
    """Clear every in-memory and filesystem ontology cache.

    Called by the API refresh endpoint so the next graph request rebuilds
    everything from disk, including re-resolving all owl:imports.
    """
    global _dynamic_uri_map_populated
    _graph_with_imports_cache.clear()
    _dynamic_uri_to_path.clear()
    _suffix_to_dynamic_path.clear()
    _dynamic_uri_map_populated = False
    # Clear the filesystem metadata cache (SPARQL label/definition look-ups).
    for _, adapter in _cache._adapters:
        cache_dir = getattr(adapter, "cache_dir", None)
        if cache_dir and Path(cache_dir).exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
            Path(cache_dir).mkdir(parents=True, exist_ok=True)


# ── Pure utility functions ────────────────────────────────────────────────────


def _load_ontology_graph(ontology_path: str, add_imports: bool = False) -> Graph:
    extension = Path(ontology_path).suffix.lower()
    parse_format = {
        ".ttl": "turtle",
        ".owl": "xml",
        ".rdf": "xml",
        ".nt": "nt",
    }.get(extension)

    graph = Graph()
    try:
        graph.parse(ontology_path, format=parse_format)
    except Exception:
        graph.parse(ontology_path)

    if add_imports:
        for import_uri in graph.objects(None, OWL.imports):
            graph_imports = Graph()
            try:
                import_path = str(import_uri)
                import_extension = Path(import_path).suffix.lower()
                import_parse_format = {
                    ".ttl": "turtle",
                    ".owl": "xml",
                    ".rdf": "xml",
                    ".nt": "nt",
                }.get(import_extension)
                graph_imports.parse(import_path, format=import_parse_format)
            except Exception as e:
                logger.error(f"Error parsing import {import_uri}: {e}")
                continue
            graph += graph_imports
    return graph


# Known remote import URIs → relative paths under the ontologies/imports/ directory
_IMPORT_URI_TO_LOCAL: dict[str, str] = {
    "http://purl.obolibrary.org/obo/bfo.owl": "top-level/bfo-core.ttl",
    "http://purl.obolibrary.org/obo/bfo/2020/bfo-core.ttl": "top-level/bfo-core.ttl",
    "https://www.commoncoreontologies.org/AgentOntology": "mid-level/AgentOntology.ttl",
    "https://www.commoncoreontologies.org/InformationEntityOntology": "mid-level/InformationEntityOntology.ttl",
    "https://www.commoncoreontologies.org/EventOntology": "mid-level/EventOntology.ttl",
    "https://www.commoncoreontologies.org/ExtendedRelationOntology": "mid-level/ExtendedRelationOntology.ttl",
    "https://www.commoncoreontologies.org/ArtifactOntology": "mid-level/ArtifactOntology.ttl",
    "https://www.commoncoreontologies.org/GeospatialOntology": "mid-level/GeospatialOntology.ttl",
    "https://www.commoncoreontologies.org/QualityOntology": "mid-level/QualityOntology.ttl",
    "https://www.commoncoreontologies.org/TimeOntology": "mid-level/TimeOntology.ttl",
    "https://www.commoncoreontologies.org/FacilityOntology": "mid-level/FacilityOntology.ttl",
    "https://www.commoncoreontologies.org/UnitsOfMeasureOntology": "mid-level/UnitsOfMeasureOntology.ttl",
}

# Public raw tree for bundled imports when the local `imports/` checkout is missing (e.g. minimal deploy).
_IMPORTS_GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/jupyter-naas/abi/refs/heads/main/"
    "libs/naas-abi/naas_abi/ontologies/imports/"
)

# Canonical ABI imports directory — used as a fallback when a workspace-local ontology
# (e.g. axi_ai, osint) doesn't have its own imports/ subdirectory.
# service.py lives at: naas_abi/apps/nexus/apps/api/app/services/ontology/service.py
# parents[7] = naas_abi/ package root.
_ABI_IMPORTS_DIR = Path(__file__).parents[7] / "ontologies" / "imports"

# Runtime map: owl:Ontology IRI → absolute local file path.
# Populated from registered module ontologies so that workspace-specific
# imports (e.g. http://ontology.naas.ai/abi/Ontology) resolve locally
# instead of triggering a network fetch.
_dynamic_uri_to_path: dict[str, str] = {}
_dynamic_uri_map_populated: bool = False

# Suffix map: "{abi:pythonPackage}/{abi:ontologyResource}" → absolute local file path.
# Handles relative file:// import URIs like <axi_ai/ontologies/modules/UAS_Act_Ontology.ttl>
# which rdflib resolves to file:///some/env-specific/path/axi_ai/ontologies/modules/...
# The resolved path won't exist on a different machine, so we match by suffix instead.
_suffix_to_dynamic_path: dict[str, str] = {}

_ABI_PYTHON_PACKAGE = URIRef("http://ontology.naas.ai/abi/pythonPackage")
_ABI_ONTOLOGY_RESOURCE = URIRef("http://ontology.naas.ai/abi/ontologyResource")

# Paths currently being resolved (cycle guard for recursive cached loads).
_currently_resolving: set[str] = set()


def _parse_format_for_suffix(suffix: str) -> str | None:
    return {
        ".ttl": "turtle",
        ".owl": "xml",
        ".rdf": "xml",
        ".nt": "nt",
    }.get(suffix.lower())


def _populate_dynamic_uri_map(ontology_paths: list[str]) -> None:
    """Map each registered ontology's IRI to its local file path.

    Called once from get_overview_graph so that _resolve_imports_into can
    resolve workspace-specific import URIs (e.g. http://ontology.naas.ai/abi/Ontology)
    to local files instead of attempting a failing network fetch.
    On first discovery of new URIs the import-resolved graph cache is cleared
    so the next load picks up the new mappings.
    """
    global _dynamic_uri_map_populated
    known_paths = set(_dynamic_uri_to_path.values())
    changed = False
    for path in ontology_paths:
        if path in known_paths:
            continue
        try:
            g = Graph()
            g.parse(path, format=_parse_format_for_suffix(Path(path).suffix) or "turtle")
            for subject in g.subjects(RDF.type, OWL.Ontology):
                uri = str(subject)
                if uri and uri not in _dynamic_uri_to_path and uri not in _IMPORT_URI_TO_LOCAL:
                    _dynamic_uri_to_path[uri] = path
                    changed = True
                # Build suffix map so relative file:// imports like
                # <axi_ai/ontologies/modules/UAS_Act_Ontology.ttl> can be resolved
                # even when rdflib expanded them against an environment-specific base path.
                pkg = g.value(subject, _ABI_PYTHON_PACKAGE)
                res = g.value(subject, _ABI_ONTOLOGY_RESOURCE)
                if pkg and res:
                    suffix = f"{pkg}/{res}"
                    if suffix not in _suffix_to_dynamic_path:
                        _suffix_to_dynamic_path[suffix] = path
                        changed = True
        except Exception as exc:
            logger.debug(f"Could not extract ontology IRI from {path}: {exc}")
    if changed:
        _graph_with_imports_cache.clear()
    _dynamic_uri_map_populated = True


def _load_ontology_graph_with_imports_cached(path: str) -> Graph:
    """Load ontology + all owl:imports using local files first; result is in-memory cached."""
    if path in _graph_with_imports_cache:
        return _graph_with_imports_cache[path]

    # Cycle guard: if this path is already being resolved up the call stack, return empty.
    if path in _currently_resolving:
        return Graph()
    _currently_resolving.add(path)

    try:
        # Derive imports/ directory from the ontology path (e.g. …/ontologies/modules/ → …/ontologies/imports/)
        imports_dir = Path(path).parent.parent / "imports"
        seen: set[str] = set()

        def _resolve_imports_into(target: Graph, source: Graph) -> None:
            for import_uri in list(source.objects(None, OWL.imports)):
                uri_str = str(import_uri)
                if uri_str in seen:
                    continue
                seen.add(uri_str)
                relative = _IMPORT_URI_TO_LOCAL.get(uri_str)
                local_path = imports_dir / relative if relative else None
                # Fallback: canonical ABI imports dir (for workspace ontologies that don't
                # ship their own imports/ directory, e.g. axi_ai, osint, marketplace apps).
                abi_local_path = _ABI_IMPORTS_DIR / relative if relative else None
                dynamic_path = _dynamic_uri_to_path.get(uri_str)
                nested = Graph()
                if local_path and local_path.exists():
                    nested = _load_ontology_graph(str(local_path))
                    target += nested
                    _resolve_imports_into(target, nested)
                elif abi_local_path and abi_local_path.exists():
                    nested = _load_ontology_graph(str(abi_local_path))
                    target += nested
                    _resolve_imports_into(target, nested)
                elif dynamic_path and Path(dynamic_path).exists():
                    # Resolve via the registered module path, using that file's own
                    # imports/ dir so its nested imports (e.g. BFO) also resolve correctly.
                    nested = _load_ontology_graph_with_imports_cached(dynamic_path)
                    target += nested
                elif relative:
                    github_url = f"{_IMPORTS_GITHUB_RAW_BASE}{relative}"
                    parse_format = _parse_format_for_suffix(Path(relative).suffix)
                    try:
                        nested.parse(github_url, format=parse_format)
                        target += nested
                        _resolve_imports_into(target, nested)
                    except Exception as e:
                        logger.error(f"Error loading import {uri_str} from {github_url}: {e}")
                        try:
                            nested = Graph()
                            nested.parse(uri_str)
                            target += nested
                        except Exception as e2:
                            logger.error(f"Error loading import {uri_str}: {e2}")
                elif uri_str.startswith("file://"):
                    # Relative import resolved by rdflib against an environment-specific
                    # base (e.g. Docker /app/src/... vs local /home/.../src/).
                    # Match by the suffix "{pythonPackage}/{ontologyResource}" which is
                    # env-independent and captured in _suffix_to_dynamic_path.
                    uri_file_path = uri_str[len("file://"):]
                    matched_path = next(
                        (dp for sfx, dp in _suffix_to_dynamic_path.items() if uri_file_path.endswith(sfx)),
                        None,
                    )
                    if matched_path:
                        nested = _load_ontology_graph_with_imports_cached(matched_path)
                        target += nested
                    else:
                        logger.warning(f"Cannot resolve file:// import {uri_str}: no matching module found")
                else:
                    try:
                        nested.parse(uri_str)
                        target += nested
                    except Exception as e:
                        logger.error(f"Error loading import {uri_str}: {e}")

        # Copy into a fresh graph so the lru_cache'd module-only graph is never mutated.
        # Without this, `graph = _load_ontology_graph(path)` would return an already-
        # polluted object (module + all imports) after the first import resolution, causing
        # the class query to find imported classes (e.g. BFO) as duplicates in the network.
        module_graph = _load_ontology_graph(path)
        g = Graph()
        g += module_graph
        _resolve_imports_into(g, g)
        _graph_with_imports_cache[path] = g
    finally:
        _currently_resolving.discard(path)

    return _graph_with_imports_cache[path]


_BFO_BUCKET_ROOTS = " ".join(
    f"<http://purl.obolibrary.org/obo/{bfo_id}>"
    for bfo_id in (
        "BFO_0000040",  # Material Entity (WHO)
        "BFO_0000015",  # Process (WHAT)
        "BFO_0000008",  # Temporal Region (WHEN)
        "BFO_0000029",  # Site (WHERE)
        "BFO_0000031",  # Generically Dependent Continuant (HOW WE KNOW)
        "BFO_0000019",  # Quality (HOW IT IS)
        "BFO_0000017",  # Realizable (WHY)
    )
)

# ABI ontology defines owl:equivalentClass aliases for the 7 BFO bucket roots.
# Their rdfs:subClassOf chains do NOT pass through the bucket root IRI (e.g.,
# abi:TemporalRegion rdfs:subClassOf bfo:BFO_0000003, not BFO_0000008), so the
# SPARQL ancestor query misses them without this explicit mapping.
_ABI_NS = "http://ontology.naas.ai/abi/"
_BFO_NS = "http://purl.obolibrary.org/obo/"
_ABI_TO_BFO_BUCKET_ROOT: dict[str, str] = {
    f"{_ABI_NS}{abi_name}": f"{_BFO_NS}{bfo_id}"
    for abi_name, bfo_id in (
        ("MaterialEntity", "BFO_0000040"),                  # WHO
        ("Site", "BFO_0000029"),                            # WHERE
        ("GenericallyDependentContinuant", "BFO_0000031"),  # HOW WE KNOW
        ("Quality", "BFO_0000019"),                         # HOW IT IS
        ("Role", "BFO_0000017"),        # BFO Role ⊆ Realizable (WHY)
        ("Disposition", "BFO_0000017"), # BFO Disposition ⊆ Realizable (WHY)
        ("Process", "BFO_0000015"),                         # WHAT
        ("TemporalRegion", "BFO_0000008"),                  # WHEN
        ("TemporalInstant", "BFO_0000008"),  # zero-dim temporal region ⊆ temporal region
    )
}
_ABI_BUCKET_VALUES = " ".join(f"<{iri}>" for iri in _ABI_TO_BFO_BUCKET_ROOT)


_BFO_ENTITY_IRIS = {
    "BFO_0000001",
    "http://purl.obolibrary.org/obo/BFO_0000001",
}


def _is_bfo_entity_iri(iri: str | None) -> bool:
    """True when iri is BFO:entity (BFO_0000001)."""
    if not iri:
        return False
    if iri in _BFO_ENTITY_IRIS:
        return True
    return iri.rstrip("/") in _BFO_ENTITY_IRIS


def _find_bfo_ancestor(graph: Graph, class_iri: str) -> str | None:
    """Walk rdfs:subClassOf+ to find the nearest BFO bucket-root ancestor, or None."""
    # Direct BFO bucket root (e.g. BFO_0000031 itself).
    if f"<{class_iri}>" in _BFO_BUCKET_ROOTS:
        return class_iri
    # ABI equivalent of a BFO bucket root (e.g. abi:TemporalRegion = BFO_0000008).
    # These classes have rdfs:subClassOf pointing ABOVE the bucket root, so the
    # transitive query below would miss them.
    if class_iri in _ABI_TO_BFO_BUCKET_ROOT:
        return _ABI_TO_BFO_BUCKET_ROOT[class_iri]

    # Walk rdfs:subClassOf+; check both BFO bucket roots and ABI equivalents so
    # that subclasses of ABI wrappers (e.g. MyClass ⊆ abi:TemporalRegion) are found
    # even when BFO itself is not in the graph.
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?ancestor WHERE {{
            VALUES ?ancestor {{ {_BFO_BUCKET_ROOTS} {_ABI_BUCKET_VALUES} }}
            <{class_iri}> rdfs:subClassOf+ ?ancestor .
        }}
        LIMIT 1
    """
    for row in graph.query(query):
        assert isinstance(row, ResultRow)
        val = getattr(row, "ancestor", None)
        if val:
            ancestor_iri = str(val)
            # If we landed on an ABI equivalent, return its canonical BFO bucket IRI.
            return _ABI_TO_BFO_BUCKET_ROOT.get(ancestor_iri, ancestor_iri)
    return None
    return None


def _compute_ontology_stats_for_graph(graph: Graph) -> tuple[int, int, int, int, int]:
    """Return (classes, object_properties, data_properties, named_individuals, imports)."""

    def _count_iri_subjects(rdf_type: URIRef) -> int:
        return len({s for s in graph.subjects(RDF.type, rdf_type) if isinstance(s, URIRef)})

    return (
        _count_iri_subjects(OWL.Class),
        _count_iri_subjects(OWL.ObjectProperty),
        _count_iri_subjects(OWL.DatatypeProperty),
        _count_iri_subjects(OWL.NamedIndividual),
        len(set(graph.objects(None, OWL.imports))),
    )


def _parse_ttl(content: str, file_path: str) -> ReferenceOntologyData:
    """Parse TTL/Turtle format ontology content."""
    classes: list[ReferenceClassData] = []
    properties: list[ReferencePropertyData] = []

    class_pattern = r"<([^>]+)>\s+a\s+owl:Class\s*;([^.]+)\."
    for match in re.finditer(class_pattern, content, re.DOTALL):
        iri = match.group(1)
        body = match.group(2)
        label_match = re.search(r'rdfs:label\s+"([^"]+)"', body)
        label = label_match.group(1) if label_match else iri.split("/")[-1]
        def_match = re.search(r'skos:definition\s+"([^"]+)"', body)
        definition = def_match.group(1) if def_match else None
        example_match = re.search(r'skos:example\s+"([^"]+)"', body)
        examples = example_match.group(1) if example_match else None
        classes.append(
            ReferenceClassData(iri=iri, label=label, definition=definition, examples=examples)
        )

    prop_pattern = r"<([^>]+)>\s+rdf:type\s+owl:ObjectProperty\s*;?([^.]*)\."
    for match in re.finditer(prop_pattern, content, re.DOTALL):
        iri = match.group(1)
        body = match.group(2)
        label_match = re.search(r'rdfs:label\s+"([^"]+)"', body)
        label = label_match.group(1) if label_match else iri.split("/")[-1]
        def_match = re.search(r'skos:definition\s+"([^"]+)"', body)
        definition = def_match.group(1) if def_match else None
        properties.append(ReferencePropertyData(iri=iri, label=label, definition=definition))

    name_match = re.search(r'dc:title\s+"([^"]+)"', content)
    name = name_match.group(1) if name_match else os.path.basename(file_path).replace(".ttl", "")

    return ReferenceOntologyData(
        id=f"ref-{int(datetime.now().timestamp() * 1000)}",
        name=name,
        file_path=file_path,
        format="ttl",
        classes=classes,
        properties=properties,
        imported_at=datetime.now(),
    )


# ── Cached triple-store helpers (module-level to keep cache decorator) ────────


def _get_uri_metadata_from_graph(graph: Graph, uri: str) -> dict:
    """Read label/definition/subClassOf etc. directly from an in-memory rdflib Graph."""
    from rdflib import Namespace
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
    subject = URIRef(uri)
    label = next((str(o) for o in graph.objects(subject, RDFS.label)), None)
    definition = next((str(o) for o in graph.objects(subject, SKOS.definition)), None)
    example = next((str(o) for o in graph.objects(subject, SKOS.example)), None)
    comment = next((str(o) for o in graph.objects(subject, RDFS.comment)), None)
    subclass_of = next(
        (str(o) for o in graph.objects(subject, RDFS.subClassOf) if isinstance(o, URIRef)),
        None,
    )
    subproperty_of = next(
        (str(o) for o in graph.objects(subject, RDFS.subPropertyOf) if isinstance(o, URIRef)),
        None,
    )
    return {
        "label": label or uri,
        "definition": definition,
        "example": example,
        "subClassOf": subclass_of,
        "subPropertyOf": subproperty_of,
        "comment": comment,
    }


@_cache(
    lambda triple_store, uri: f"metadata_uri_{uri}",
    DataType.JSON,
    ttl=timedelta(days=1),
)
def _get_uri_metadata(triple_store: TripleStoreService, uri: str) -> dict:
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?label ?definition ?example ?subClassOf ?subPropertyOf ?comment
    WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            OPTIONAL {{ <{uri}> rdfs:label ?label . }}
            OPTIONAL {{ <{uri}> skos:definition ?definition . }}
            OPTIONAL {{ <{uri}> skos:example ?example . }}
            OPTIONAL {{ <{uri}> rdfs:comment ?comment . }}
            OPTIONAL {{
                <{uri}> rdfs:subClassOf ?subClassOf .
                FILTER(isIRI(?subClassOf))
            }}
            OPTIONAL {{
                <{uri}> rdfs:subPropertyOf ?subPropertyOf .
                FILTER(isIRI(?subPropertyOf))
            }}
        }}
    }}
    """
    result: dict = {}
    for row in triple_store.query(query):
        assert isinstance(row, ResultRow)
        result = {
            "label": str(row.label) if row.label else uri,
            "definition": str(row.definition) if row.definition else None,
            "example": str(row.example) if row.example else None,
            "subClassOf": str(row.subClassOf) if row.subClassOf else None,
            "subPropertyOf": str(row.subPropertyOf) if row.subPropertyOf else None,
            "comment": str(row.comment) if row.comment else None,
        }
    return result


def _get_ontology_metadata(triple_store: TripleStoreService, ontology_iri: str) -> dict:
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dc: <http://purl.org/dc/terms/>
    PREFIX dc11: <http://purl.org/dc/elements/1.1/>
    SELECT ?label ?comment ?versionInfo ?title ?description ?license ?date
    WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            <{ontology_iri}> rdf:type owl:Ontology .
            OPTIONAL {{ <{ontology_iri}> rdfs:label ?label . }}
            OPTIONAL {{ <{ontology_iri}> rdfs:comment ?comment . }}
            OPTIONAL {{ <{ontology_iri}> owl:versionInfo ?versionInfo . }}
            OPTIONAL {{ <{ontology_iri}> dc:title ?title . }}
            OPTIONAL {{ <{ontology_iri}> dc:description ?description . }}
            OPTIONAL {{ <{ontology_iri}> dc:license ?license . }}
            OPTIONAL {{ <{ontology_iri}> dc11:date ?date . }}
        }}
    }}
    """
    result: dict = {}
    for row in triple_store.query(query):
        assert isinstance(row, ResultRow)
        result.update(
            {
                "label": str(row.label) if getattr(row, "label", None) else None,
                "comment": str(row.comment) if getattr(row, "comment", None) else None,
                "versionInfo": str(row.versionInfo) if getattr(row, "versionInfo", None) else None,
                "title": str(row.title) if getattr(row, "title", None) else None,
                "description": str(row.description) if getattr(row, "description", None) else None,
                "license": str(row.license) if getattr(row, "license", None) else None,
                "date": str(row.date) if getattr(row, "date", None) else None,
            }
        )
    return result


# ── Service ───────────────────────────────────────────────────────────────────


class OntologyService:
    def __init__(
        self,
        triple_store_getter: Callable[[], TripleStoreService] | None = None,
        abi_module_getter: Callable[[], Any] | None = None,
    ) -> None:
        self._triple_store_getter = triple_store_getter
        self._abi_module_getter = abi_module_getter
        # In-memory storage (replace with persistence later)
        self._ontology_items: list[OntologyItemData] = []

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_triple_store(self) -> TripleStoreService:
        if self._triple_store_getter is not None:
            return self._triple_store_getter()
        try:
            from naas_abi import ABIModule

            return ABIModule.get_instance().engine.services.triple_store
        except Exception as exc:
            raise OntologyServiceUnavailableError(
                "Triple store is not initialized. Load API through naas_abi.ABIModule."
            ) from exc

    def _get_abi_module(self) -> Any:
        if self._abi_module_getter is not None:
            return self._abi_module_getter()
        try:
            from naas_abi import ABIModule

            return ABIModule.get_instance()
        except Exception as exc:
            raise OntologyServiceUnavailableError("ABIModule is not initialized.") from exc

    def _resolve_ontology_paths(
        self, ontology_path: str | None, ontologies: list[OntologyFileItemData]
    ) -> list[str]:
        all_paths = [item.path for item in ontologies]
        if ontology_path:
            if ontology_path not in all_paths:
                raise OntologyPathNotFoundError(f"Ontology path not found: {ontology_path}")
            return [ontology_path]
        return all_paths

    # ── Public API ────────────────────────────────────────────────────────────

    async def clear_cache(self) -> None:
        """Clear all in-memory and filesystem ontology graph caches."""
        clear_graph_caches()

    async def list_items(self) -> list[OntologyItemData]:
        """List all ontology items (OWL Classes and Object Properties)."""
        classes = await self.list_classes(ontology_path=None)
        relations = await self.list_relations(ontology_path=None)
        return [*classes, *relations]

    async def list_classes(self, ontology_path: str | None) -> list[OntologyItemData]:
        """List ontology classes (owl:Class) across registered ontology files."""
        ontologies = await self.list_ontology_files()
        target_paths = self._resolve_ontology_paths(ontology_path, ontologies)
        by_iri: dict[str, OntologyItemData] = {}

        query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?s WHERE {
                ?s rdf:type owl:Class .
                FILTER(isIRI(?s))
            }
        """
        for path in target_paths:
            graph = _load_ontology_graph(path)
            for row in graph.query(query):
                assert isinstance(row, ResultRow)
                iri = str(row.get("s"))
                if iri in by_iri:
                    continue
                data = _get_uri_metadata_from_graph(graph, iri)
                label = data.get("label", "Unknown")
                definition = data.get("definition")
                comment = data.get("comment", "Unknown")
                example = data.get("example", "Unknown")
                parent_id = data.get("subClassOf", "Unknown")
                parent_data = _get_uri_metadata_from_graph(graph, parent_id) if parent_id else None
                parent_label = parent_data.get("label", "Unknown") if parent_data else None
                if _is_bfo_entity_iri(iri):
                    parent_id = None
                    parent_label = None
                by_iri[iri] = OntologyItemData(
                    id=iri,
                    name=label,
                    type="Class",
                    description=str(definition) if definition else str(comment),
                    example=str(example),
                    parent_id=str(parent_id) if parent_id is not None else None,
                    parent_name=str(parent_label) if parent_label is not None else None,
                )
        return sorted(by_iri.values(), key=lambda item: item.name.lower())

    async def list_relations(self, ontology_path: str | None) -> list[OntologyItemData]:
        """List ontology object properties (owl:ObjectProperty) across registered ontology files."""
        ontologies = await self.list_ontology_files()
        target_paths = self._resolve_ontology_paths(ontology_path, ontologies)
        by_iri: dict[str, OntologyItemData] = {}

        query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?s WHERE {
                ?s rdf:type owl:ObjectProperty .
                FILTER(isIRI(?s))
            }
        """
        for path in target_paths:
            graph = _load_ontology_graph(path)
            for row in graph.query(query):
                assert isinstance(row, ResultRow)
                iri = str(row.get("s"))
                if iri in by_iri:
                    continue
                data = _get_uri_metadata_from_graph(graph, iri)
                label = data.get("label", "Unknown")
                definition = data.get("definition", "Unknown")
                comment = data.get("comment", "Unknown")
                parent_id = data.get("subPropertyOf", "Unknown")
                parent_data = _get_uri_metadata_from_graph(graph, parent_id) if parent_id else None
                parent_label = parent_data.get("label", "Unknown") if parent_data else None
                by_iri[iri] = OntologyItemData(
                    id=iri,
                    name=label,
                    type="Object Property",
                    description=str(definition) if definition else str(comment),
                    parent_id=str(parent_id),
                    parent_name=str(parent_label),
                )
        return sorted(by_iri.values(), key=lambda item: item.name.lower())

    async def list_ontology_files(self) -> list[OntologyFileItemData]:
        """List ontology files from all registered modules."""
        from rdflib import DCTERMS, OWL, RDF, Graph, URIRef

        try:
            abi_module = self._get_abi_module()
            abi_ontologies: list[str] = list(abi_module.ontologies)
            for module in abi_module.engine.modules.values():
                abi_ontologies.extend(module.ontologies)

            ontology_files: list[OntologyFileItemData] = []
            seen: set[str] = set()

            for ontology in abi_ontologies:
                if ontology in seen:
                    continue
                seen.add(ontology)

                if "sandbox" in ontology.lower() or "modules" not in ontology.lower():
                    continue

                ontology_graph = Graph()
                ontology_graph.parse(ontology, format="turtle")

                ontology_uri = next(ontology_graph.subjects(RDF.type, OWL.Ontology), None)
                if ontology_uri is None:
                    continue

                title = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.title)
                label = ontology_graph.value(URIRef(str(ontology_uri)), RDFS.label)
                description = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.description)
                license_val = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.license)
                contributors = list(
                    ontology_graph.objects(URIRef(str(ontology_uri)), DCTERMS.contributor)
                )
                date = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.date)
                imports = list(ontology_graph.objects(URIRef(str(ontology_uri)), OWL.imports))

                parts = ontology.split("/")
                try:
                    idx = parts.index("ontologies")
                    module_name = parts[idx - 1] if idx > 0 else ""
                except ValueError:
                    module_name = parts[0] if parts else ""

                ontology_files.append(
                    OntologyFileItemData(
                        name=str(title) if title else str(label),
                        description=str(description) if description else None,
                        license=str(license_val) if license_val else None,
                        contributors=[str(c) for c in contributors],
                        date=str(date) if date else None,
                        path=ontology,
                        module_name=module_name.replace("_", " "),
                        submodule_name=None,
                        imports=[str(i) for i in imports],
                    )
                )

            ontology_files.sort(key=lambda item: (item.module_name.lower(), item.name.lower()))
            return ontology_files
        except OntologyServiceUnavailableError:
            raise
        except Exception as exc:
            raise OntologyServiceUnavailableError("Failed to list ontology files") from exc

    async def get_overview_stats(self, ontology_path: str) -> OntologyOverviewStatsData:
        """Return element counts for a specific ontology file."""
        try:
            graph = _load_ontology_graph(ontology_path)
            classes, obj_props, data_props, named_ind, imports = _compute_ontology_stats_for_graph(
                graph
            )
            return OntologyOverviewStatsData(
                name=Path(ontology_path).name,
                path=ontology_path,
                total_items=classes + obj_props + data_props + named_ind,
                classes=classes,
                object_properties=obj_props,
                data_properties=data_props,
                named_individuals=named_ind,
                imports=imports,
            )
        except Exception as exc:
            raise OntologyServiceUnavailableError(
                "Failed to compute ontology overview stats"
            ) from exc

    async def get_all_overview_stats(self) -> OntologyOverviewAggregateStatsData:
        """Return consolidated stats across all registered ontology files."""
        try:
            ontologies = await self.list_ontology_files()
            totals = [0, 0, 0, 0, 0]  # classes, obj_props, data_props, named_ind, imports
            for item in ontologies:
                try:
                    graph = _load_ontology_graph(item.path)
                    counts = _compute_ontology_stats_for_graph(graph)
                    for i, v in enumerate(counts):
                        totals[i] += v
                except Exception:
                    continue
            return OntologyOverviewAggregateStatsData(
                name="All ontologies",
                path="*",
                ontologies_count=len(ontologies),
                total_items=totals[0] + totals[1] + totals[2] + totals[3],
                classes=totals[0],
                object_properties=totals[1],
                data_properties=totals[2],
                named_individuals=totals[3],
                imports=totals[4],
            )
        except OntologyServiceUnavailableError:
            raise
        except Exception as exc:
            raise OntologyServiceUnavailableError(
                "Failed to compute aggregate ontology stats"
            ) from exc

    async def get_type_counts(self, ontology_path: str | None) -> OntologyTypeCountsData:
        """Return NamedIndividual and DatatypeProperty counts."""
        try:
            ontologies = await self.list_ontology_files()
            target_paths = self._resolve_ontology_paths(ontology_path, ontologies)
            named_individuals = 0
            data_properties = 0
            for path in target_paths:
                graph = _load_ontology_graph(path)
                named_individuals += len(set(graph.subjects(RDF.type, OWL.NamedIndividual)))
                data_properties += len(set(graph.subjects(RDF.type, OWL.DatatypeProperty)))
            return OntologyTypeCountsData(
                name=Path(ontology_path).name if ontology_path else "All ontologies",
                path=ontology_path or "*",
                data_properties=data_properties,
                named_individuals=named_individuals,
            )
        except (OntologyPathNotFoundError, OntologyServiceUnavailableError):
            raise
        except Exception as exc:
            raise OntologyServiceUnavailableError("Failed to compute ontology type counts") from exc

    async def get_overview_graph(self, ontology_path: str | None) -> OntologyOverviewGraphData:
        """Return ontology dependency/class graph."""
        store = self._get_triple_store()
        try:
            ontologies = await self.list_ontology_files()
            _populate_dynamic_uri_map([item.path for item in ontologies])
            target_paths = self._resolve_ontology_paths(ontology_path, ontologies)

            if ontology_path:
                # Single ontology: show classes + object properties
                classes_by_iri: dict[str, OntologyOverviewGraphNodeData] = {}
                edges_by_id: dict[str, OntologyOverviewGraphEdgeData] = {}
                collected_prefixes: dict[str, str] = {}

                class_query = """
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX owl: <http://www.w3.org/2002/07/owl#>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    SELECT ?classIri WHERE {
                        ?classIri rdf:type owl:Class .
                        FILTER(isIRI(?classIri))
                    }
                """
                relation_query = """
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX owl: <http://www.w3.org/2002/07/owl#>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    SELECT DISTINCT ?propertyIri ?propertyLabel ?propertyDefinition ?domain ?range ?parentPropertyIri WHERE {
                        ?propertyIri rdf:type owl:ObjectProperty .
                        FILTER(isIRI(?propertyIri))
                        OPTIONAL { ?propertyIri rdfs:label ?propertyLabel . }
                        OPTIONAL { ?propertyIri skos:definition ?propertyDefinition . }
                        OPTIONAL {
                            {
                                ?propertyIri rdfs:domain ?domain .
                                FILTER(isIRI(?domain))
                            }
                            UNION
                            {
                                ?propertyIri rdfs:domain ?domainUnion .
                                ?domainUnion owl:unionOf/rdf:rest*/rdf:first ?domain .
                                FILTER(isIRI(?domain))
                            }
                        }
                        OPTIONAL {
                            {
                                ?propertyIri rdfs:range ?range .
                                FILTER(isIRI(?range))
                            }
                            UNION
                            {
                                ?propertyIri rdfs:range ?rangeUnion .
                                ?rangeUnion owl:unionOf/rdf:rest*/rdf:first ?range .
                                FILTER(isIRI(?range))
                            }
                        }
                        OPTIONAL {
                            ?propertyIri rdfs:subPropertyOf ?parentPropertyIri .
                            FILTER(isIRI(?parentPropertyIri))
                        }
                    }
                """

                for path in target_paths:
                    # module-only graph: used for all queries (classes, properties, restrictions)
                    graph = _load_ontology_graph(path)
                    # imports graph: used only for BFO ancestor resolution — not for queries
                    ancestor_graph = _load_ontology_graph_with_imports_cached(path)

                    for prefix, namespace in graph.namespaces():
                        p = str(prefix)
                        if p and p not in collected_prefixes:
                            collected_prefixes[p] = str(namespace)

                    for row in graph.query(class_query):
                        assert isinstance(row, ResultRow)
                        class_iri = str(row.get("classIri"))
                        if not class_iri or class_iri in classes_by_iri:
                            continue
                        data = _get_uri_metadata_from_graph(ancestor_graph, class_iri)
                        class_label = data.get("label", "Unknown")
                        definition = data.get("definition")
                        comment = data.get("comment", "Unknown")
                        parent_iri = data.get("subClassOf", "Unknown")
                        parent_data = _get_uri_metadata_from_graph(ancestor_graph, parent_iri) if parent_iri else None
                        parent_label = parent_data.get("label", "Unknown") if parent_data else None
                        if _is_bfo_entity_iri(class_iri):
                            parent_iri = class_iri
                            parent_label = "entity"
                        bfo_ancestor = _find_bfo_ancestor(ancestor_graph, class_iri)
                        classes_by_iri[class_iri] = OntologyOverviewGraphNodeData(
                            id=class_iri,
                            label=class_label,
                            type=parent_label,
                            properties={
                                "iri": class_iri,
                                "definition": str(definition) if definition else str(comment),
                                "comment": str(comment),
                                "parent_iri": str(parent_iri),
                                "parent_label": str(parent_label),
                                "bfo_parent_iri": bfo_ancestor or "",
                                "is_primary": True,
                            },
                        )

                    restriction_query = """
                        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                        PREFIX owl: <http://www.w3.org/2002/07/owl#>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                        SELECT DISTINCT ?classIri ?propertyIri ?propertyLabel ?targetIri WHERE {
                            ?classIri rdfs:subClassOf ?restriction .
                            ?restriction a owl:Restriction ;
                                         owl:onProperty ?propertyIri .
                            {
                                { ?restriction owl:someValuesFrom ?targetIri . FILTER(isIRI(?targetIri)) }
                                UNION
                                { ?restriction owl:allValuesFrom ?targetIri . FILTER(isIRI(?targetIri)) }
                                UNION
                                { ?restriction owl:hasValue ?targetIri . FILTER(isIRI(?targetIri)) }
                                UNION
                                { ?restriction owl:someValuesFrom ?unionClass . ?unionClass owl:unionOf/rdf:rest*/rdf:first ?targetIri . FILTER(isIRI(?targetIri)) }
                                UNION
                                { ?restriction owl:allValuesFrom ?unionClass . ?unionClass owl:unionOf/rdf:rest*/rdf:first ?targetIri . FILTER(isIRI(?targetIri)) }
                            }
                            OPTIONAL { ?propertyIri rdfs:label ?propertyLabel . }
                            FILTER(isIRI(?classIri))
                            FILTER(isIRI(?propertyIri))
                        }
                    """

                    def _make_node(
                        iri: str, _ag: Graph = ancestor_graph
                    ) -> OntologyOverviewGraphNodeData:
                        d = _get_uri_metadata_from_graph(_ag, iri)
                        lbl = d.get("label", "Unknown")
                        typ = d.get("subClassOf")
                        typ_lbl = (
                            _get_uri_metadata_from_graph(_ag, typ).get("label", "Unknown") if typ else None
                        )
                        if _is_bfo_entity_iri(iri):
                            typ = iri
                            typ_lbl = "entity"
                        defn = d.get("definition")
                        cmnt = d.get("comment")
                        bfo_ancestor = _find_bfo_ancestor(_ag, iri)
                        return OntologyOverviewGraphNodeData(
                            id=iri,
                            label=str(lbl),
                            type=typ_lbl,
                            properties={
                                "iri": iri,
                                "definition": str(defn) if defn else str(cmnt),
                                "parent_iri": str(typ),
                                "parent_label": str(typ_lbl),
                                "bfo_parent_iri": bfo_ancestor or "",
                                "is_primary": False,
                            },
                        )

                    for row in graph.query(relation_query):
                        assert isinstance(row, ResultRow)
                        property_iri = str(row.get("propertyIri"))
                        if not property_iri:
                            continue
                        source_iri = str(row.get("domain")) if row.get("domain") else None
                        target_iri = str(row.get("range")) if row.get("range") else None
                        if not source_iri or not target_iri:
                            continue
                        if source_iri not in classes_by_iri:
                            classes_by_iri[source_iri] = _make_node(source_iri)
                        if target_iri not in classes_by_iri:
                            classes_by_iri[target_iri] = _make_node(target_iri)

                        property_label = (
                            str(row.get("propertyLabel"))
                            if row.get("propertyLabel")
                            else property_iri.split("/")[-1]
                        )
                        edge_id = f"{source_iri}|{property_iri}|{target_iri}"
                        if edge_id in edges_by_id:
                            continue
                        property_definition = (
                            str(row.get("propertyDefinition"))
                            if row.get("propertyDefinition")
                            else ""
                        )
                        parent_property_iri = (
                            str(row.get("parentPropertyIri"))
                            if row.get("parentPropertyIri")
                            else ""
                        )
                        edges_by_id[edge_id] = OntologyOverviewGraphEdgeData(
                            id=edge_id,
                            source=source_iri,
                            target=target_iri,
                            type=property_label,
                            label=property_label,
                            properties={
                                "relation_kind": "object_property",
                                "iri": property_iri,
                                "definition": property_definition,
                                "parent_property_iri": parent_property_iri,
                            },
                        )

                    for row in graph.query(restriction_query):
                        assert isinstance(row, ResultRow)
                        class_iri = str(row.get("classIri")) if row.get("classIri") else None
                        property_iri = (
                            str(row.get("propertyIri")) if row.get("propertyIri") else None
                        )
                        target_iri = str(row.get("targetIri")) if row.get("targetIri") else None
                        if not class_iri or not property_iri or not target_iri:
                            continue

                        if class_iri not in classes_by_iri:
                            classes_by_iri[class_iri] = _make_node(class_iri)
                        if target_iri not in classes_by_iri:
                            classes_by_iri[target_iri] = _make_node(target_iri)

                        property_label = (
                            str(row.get("propertyLabel"))
                            if row.get("propertyLabel")
                            else property_iri.split("/")[-1]
                        )
                        edge_id = f"{class_iri}|restriction|{property_iri}|{target_iri}"
                        if edge_id in edges_by_id:
                            continue
                        prop_data = _get_uri_metadata_from_graph(ancestor_graph, property_iri)
                        prop_definition = prop_data.get("definition", "")
                        edges_by_id[edge_id] = OntologyOverviewGraphEdgeData(
                            id=edge_id,
                            source=class_iri,
                            target=target_iri,
                            type="Restriction",
                            label=property_label,
                            properties={
                                "relation_kind": "restriction",
                                "iri": property_iri,
                                "definition": str(prop_definition) if prop_definition else "",
                                "parent_property_iri": "",
                            },
                        )

                # Dedup owl:equivalentClass pairs — both the ABI wrapper and its BFO
                # counterpart may appear as separate nodes when e.g. abi:Agent has
                # rdfs:subClassOf bfo:BFO_0000040 while abi:MaterialEntity is the
                # canonical equivalent. Keep the ABI IRI; remap any edges.
                equiv_map: dict[str, str] = {}
                for sg, _, og in graph.triples((None, OWL.equivalentClass, None)):
                    if not isinstance(sg, URIRef) or not isinstance(og, URIRef):
                        continue
                    s_str, o_str = str(sg), str(og)
                    if s_str not in classes_by_iri or o_str not in classes_by_iri:
                        continue
                    non_canon, canon = (o_str, s_str) if s_str.startswith(_ABI_NS) else (s_str, o_str)
                    equiv_map[non_canon] = canon

                for non_canon in list(equiv_map):
                    classes_by_iri.pop(non_canon, None)

                for eid in list(edges_by_id):
                    edge = edges_by_id[eid]
                    new_src = equiv_map.get(edge.source, edge.source)
                    new_tgt = equiv_map.get(edge.target, edge.target)
                    if new_src != edge.source or new_tgt != edge.target:
                        del edges_by_id[eid]
                        if new_src != new_tgt:
                            new_eid = f"{new_src}|{edge.type}|{new_tgt}"
                            if new_eid not in edges_by_id:
                                edges_by_id[new_eid] = OntologyOverviewGraphEdgeData(
                                    id=new_eid,
                                    source=new_src,
                                    target=new_tgt,
                                    type=edge.type,
                                    label=edge.label,
                                    properties=dict(edge.properties),
                                )

                return OntologyOverviewGraphData(
                    nodes=sorted(classes_by_iri.values(), key=lambda n: n.label.lower()),
                    edges=sorted(edges_by_id.values(), key=lambda e: e.label.lower()),
                    prefixes=collected_prefixes,
                )

            # All ontologies: show import dependency graph
            all_graphs = Graph()
            ontologies_by_iri: dict[str, OntologyOverviewGraphNodeData] = {}
            edges_by_id = {}

            def _label_from_iri(iri: str) -> str:
                if "#" in iri:
                    return iri.rsplit("#", 1)[-1]
                return iri.rstrip("/").rsplit("/", 1)[-1]

            for path in target_paths:
                graph = _load_ontology_graph(path)
                all_graphs += graph

                for subject in graph.subjects(RDF.type, OWL.Ontology):
                    ontology_iri = str(subject)
                    if not ontology_iri or ontology_iri in ontologies_by_iri:
                        continue
                    meta = _get_ontology_metadata(store, ontology_iri)
                    title = meta.get("title", "")
                    label = meta.get("label", "")
                    properties: dict[str, str] = {"iri": ontology_iri, "source_path": path}
                    if label:
                        properties["label"] = str(label)
                    elif title:
                        properties["title"] = str(title)
                    for key in ("description", "comment", "versionInfo", "license", "date"):
                        val = meta.get(key)
                        if val:
                            properties[key] = str(val)
                    ontologies_by_iri[ontology_iri] = OntologyOverviewGraphNodeData(
                        id=ontology_iri,
                        label=str(title) if title else str(label),
                        type="Ontology",
                        properties=properties,
                    )

            imports_query = """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT ?sourceOntology ?targetOntology WHERE {
                    ?sourceOntology rdf:type owl:Ontology .
                    ?sourceOntology owl:imports ?targetOntology .
                    FILTER(isIRI(?sourceOntology) && isIRI(?targetOntology))
                }
            """
            for row in all_graphs.query(imports_query):
                assert isinstance(row, ResultRow)
                source_iri = str(row.get("sourceOntology")) if row.get("sourceOntology") else ""
                target_iri = str(row.get("targetOntology")) if row.get("targetOntology") else ""
                if not source_iri or not target_iri:
                    continue
                for iri in (source_iri, target_iri):
                    if iri not in ontologies_by_iri:
                        ontologies_by_iri[iri] = OntologyOverviewGraphNodeData(
                            id=iri,
                            label=_label_from_iri(iri),
                            type="Imports",
                            properties={"iri": iri},
                        )
                edge_id = f"{source_iri}|imports|{target_iri}"
                if edge_id not in edges_by_id:
                    edges_by_id[edge_id] = OntologyOverviewGraphEdgeData(
                        id=edge_id,
                        source=source_iri,
                        target=target_iri,
                        type="imports",
                        label="imports",
                        properties={
                            "relation_kind": "imports",
                            "iri": str(OWL.imports),
                            "definition": "Ontology import dependency.",
                            "parent_property_iri": "",
                        },
                    )

            all_prefixes: dict[str, str] = {}
            for prefix, namespace in all_graphs.namespaces():
                p = str(prefix)
                if p and p not in all_prefixes:
                    all_prefixes[p] = str(namespace)

            return OntologyOverviewGraphData(
                nodes=sorted(ontologies_by_iri.values(), key=lambda n: n.label.lower()),
                edges=sorted(edges_by_id.values(), key=lambda e: e.label.lower()),
                prefixes=all_prefixes,
            )

        except (OntologyPathNotFoundError, OntologyServiceUnavailableError):
            raise
        except Exception as exc:
            mode = "single_ontology" if ontology_path else "imports_overview"
            raise OntologyServiceUnavailableError(
                f"Failed to compute ontology overview graph ({mode}): "
                f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            ) from exc

    async def get_class_parents(
        self,
        class_iris: list[str],
        ontology_path: str,
    ) -> OntologyOverviewGraphData:
        """Return direct rdfs:subClassOf parents for the given class IRIs.

        Uses the imports-resolved graph so parents from BFO/CCO layers are
        reachable at every level of progressive expansion.
        """
        if not class_iris:
            return OntologyOverviewGraphData(nodes=[], edges=[])

        ancestor_graph = _load_ontology_graph_with_imports_cached(ontology_path)

        # Build equivalence normalisation map: BFO IRI → canonical ABI IRI
        _cp_equiv: dict[str, str] = {}
        for sg, _, og in ancestor_graph.triples((None, OWL.equivalentClass, None)):
            if not isinstance(sg, URIRef) or not isinstance(og, URIRef):
                continue
            s_str, o_str = str(sg), str(og)
            if s_str.startswith(_ABI_NS) and not o_str.startswith(_ABI_NS):
                _cp_equiv[o_str] = s_str
            elif o_str.startswith(_ABI_NS) and not s_str.startswith(_ABI_NS):
                _cp_equiv[s_str] = o_str

        def _cp_canon(iri: str) -> str:
            seen: set[str] = set()
            while iri in _cp_equiv and iri not in seen:
                seen.add(iri)
                iri = _cp_equiv[iri]
            return iri

        new_nodes: dict[str, OntologyOverviewGraphNodeData] = {}
        new_edges: dict[str, OntologyOverviewGraphEdgeData] = {}

        iris_values = " ".join(f"<{iri}>" for iri in class_iris)
        query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?subClass ?superClass WHERE {{
                VALUES ?subClass {{ {iris_values} }}
                ?subClass rdfs:subClassOf ?superClass .
                FILTER(isIRI(?superClass))
            }}
        """

        for row in ancestor_graph.query(query):
            assert isinstance(row, ResultRow)
            sub_iri = str(row.get("subClass")) if row.get("subClass") else None
            super_iri = str(row.get("superClass")) if row.get("superClass") else None
            if not sub_iri or not super_iri:
                continue
            sub_iri = _cp_canon(sub_iri)
            super_iri = _cp_canon(super_iri)
            if sub_iri == super_iri:
                continue

            if super_iri not in new_nodes:
                d = _get_uri_metadata_from_graph(ancestor_graph, super_iri)
                raw_lbl = d.get("label")
                lbl = raw_lbl or super_iri.rstrip("/").rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                typ = d.get("subClassOf")
                typ_lbl = _get_uri_metadata_from_graph(ancestor_graph, typ).get("label", "Unknown") if typ else None
                if _is_bfo_entity_iri(super_iri):
                    typ = super_iri
                    typ_lbl = "entity"
                bfo_anc = _find_bfo_ancestor(ancestor_graph, super_iri)
                new_nodes[super_iri] = OntologyOverviewGraphNodeData(
                    id=super_iri,
                    label=str(lbl),
                    type=typ_lbl,
                    properties={
                        "iri": super_iri,
                        "definition": str(d.get("definition", "")),
                        "parent_iri": str(typ) if typ else "",
                        "parent_label": str(typ_lbl) if typ_lbl else "",
                        "bfo_parent_iri": bfo_anc or "",
                        "is_primary": False,
                    },
                )

            edge_id = f"{sub_iri}|is_a|{super_iri}"
            if edge_id not in new_edges:
                new_edges[edge_id] = OntologyOverviewGraphEdgeData(
                    id=edge_id,
                    source=sub_iri,
                    target=super_iri,
                    type="is a",
                    label="is a",
                    properties={
                        "relation_kind": "is_a",
                        "iri": str(RDFS.subClassOf),
                        "definition": "",
                        "parent_property_iri": "",
                    },
                )

        return OntologyOverviewGraphData(
            nodes=list(new_nodes.values()),
            edges=list(new_edges.values()),
        )

    async def get_subclassof_hierarchy(
        self,
        class_iris: list[str],
        ontology_path: str,
    ) -> OntologyOverviewGraphData:
        """Return the full rdfs:subClassOf hierarchy for the given class IRIs.

        Walks rdfs:subClassOf transitively upward from class_iris and returns
        every (start class + ancestor) node together with every is_a edge
        between them. Each node's ``properties`` dict is annotated with a
        1-based ``level`` key derived from BFS:

          * BFO:entity (BFO_0000001) is level 1.
          * Any other root (no rdfs:subClassOf parent in the closure) is level 1.
          * A child's level is ``min(existing, parent_level + 1)``.

        Cycles and disconnected nodes default to level 1.
        """
        if not class_iris:
            return OntologyOverviewGraphData(nodes=[], edges=[])

        ancestor_graph = _load_ontology_graph_with_imports_cached(ontology_path)

        # 1. Collect every (sub, super) edge in the upward closure with one SPARQL query.
        iris_values = " ".join(f"<{iri}>" for iri in class_iris)
        closure_query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?subClass ?superClass WHERE {{
                VALUES ?startClass {{ {iris_values} }}
                ?startClass rdfs:subClassOf* ?subClass .
                ?subClass rdfs:subClassOf ?superClass .
                FILTER(isIRI(?subClass))
                FILTER(isIRI(?superClass))
            }}
        """

        edges_raw: list[tuple[str, str]] = []
        node_iris: set[str] = set(class_iris)
        for row in ancestor_graph.query(closure_query):
            assert isinstance(row, ResultRow)
            sub_iri = str(row.get("subClass")) if row.get("subClass") else None
            super_iri = str(row.get("superClass")) if row.get("superClass") else None
            if not sub_iri or not super_iri:
                continue
            edges_raw.append((sub_iri, super_iri))
            node_iris.add(sub_iri)
            node_iris.add(super_iri)

        # Normalise BFO/foreign IRIs to their ABI owl:equivalentClass counterparts
        # so that e.g. bfo:BFO_0000040 (material entity) and abi:MaterialEntity
        # don't appear as two separate nodes.
        _equiv_norm: dict[str, str] = {}
        for sg, _, og in ancestor_graph.triples((None, OWL.equivalentClass, None)):
            if not isinstance(sg, URIRef) or not isinstance(og, URIRef):
                continue
            s_str, o_str = str(sg), str(og)
            if s_str.startswith(_ABI_NS) and not o_str.startswith(_ABI_NS):
                _equiv_norm[o_str] = s_str
            elif o_str.startswith(_ABI_NS) and not s_str.startswith(_ABI_NS):
                _equiv_norm[s_str] = o_str

        def _canon(iri: str) -> str:
            seen: set[str] = set()
            while iri in _equiv_norm and iri not in seen:
                seen.add(iri)
                iri = _equiv_norm[iri]
            return iri

        edges_raw = [(_canon(s), _canon(t)) for s, t in edges_raw]
        edges_raw = [(s, t) for s, t in edges_raw if s != t]
        node_iris = {_canon(iri) for iri in node_iris}

        # 2. BFS from BFO:entity (and any other roots) to compute levels.
        bfo_entity_iri = "http://purl.obolibrary.org/obo/BFO_0000001"
        parents_by_child: dict[str, set[str]] = {}
        children_by_parent: dict[str, set[str]] = {}
        for sub, sup in edges_raw:
            parents_by_child.setdefault(sub, set()).add(sup)
            children_by_parent.setdefault(sup, set()).add(sub)

        levels: dict[str, int] = {}
        queue: list[tuple[str, int]] = []

        if bfo_entity_iri in node_iris:
            levels[bfo_entity_iri] = 1
            queue.append((bfo_entity_iri, 1))

        for iri in node_iris:
            if iri in levels:
                continue
            if not parents_by_child.get(iri):
                levels[iri] = 1
                queue.append((iri, 1))

        while queue:
            iri, level = queue.pop(0)
            for child in children_by_parent.get(iri, ()):
                next_level = level + 1
                existing = levels.get(child)
                if existing is None or next_level < existing:
                    levels[child] = next_level
                    queue.append((child, next_level))

        # Any cycle/disconnected leftovers default to level 1.
        for iri in node_iris:
            levels.setdefault(iri, 1)

        # 3. Build node + edge result objects.
        primary_iris = set(class_iris)
        result_nodes: dict[str, OntologyOverviewGraphNodeData] = {}
        for iri in node_iris:
            d = _get_uri_metadata_from_graph(ancestor_graph, iri)
            raw_lbl = d.get("label")
            label = raw_lbl or iri.rstrip("/").rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            parent_iri = d.get("subClassOf")
            parent_label = (
                _get_uri_metadata_from_graph(ancestor_graph, parent_iri).get("label", "Unknown") if parent_iri else None
            )
            if _is_bfo_entity_iri(iri):
                parent_iri = iri
                parent_label = "entity"
            bfo_anc = _find_bfo_ancestor(ancestor_graph, iri)
            result_nodes[iri] = OntologyOverviewGraphNodeData(
                id=iri,
                label=str(label),
                type=parent_label,
                properties={
                    "iri": iri,
                    "definition": str(d.get("definition", "")),
                    "comment": str(d.get("comment", "")),
                    "parent_iri": str(parent_iri) if parent_iri else "",
                    "parent_label": str(parent_label) if parent_label else "",
                    "bfo_parent_iri": bfo_anc or "",
                    "is_primary": iri in primary_iris,
                    "level": levels[iri],
                },
            )

        result_edges: dict[str, OntologyOverviewGraphEdgeData] = {}
        for sub_iri, super_iri in edges_raw:
            edge_id = f"{sub_iri}|is_a|{super_iri}"
            if edge_id in result_edges:
                continue
            result_edges[edge_id] = OntologyOverviewGraphEdgeData(
                id=edge_id,
                source=sub_iri,
                target=super_iri,
                type="is a",
                label="is a",
                properties={
                    "relation_kind": "is_a",
                    "iri": str(RDFS.subClassOf),
                    "definition": "",
                    "parent_property_iri": "",
                },
            )

        return OntologyOverviewGraphData(
            nodes=list(result_nodes.values()),
            edges=list(result_edges.values()),
        )

    async def create_entity(
        self,
        name: str,
        description: str | None,
        base_class: str | None,
    ) -> OntologyItemData:
        item = OntologyItemData(
            id=f"entity-{int(datetime.now().timestamp() * 1000)}",
            name=name,
            type="entity",
            description=description,
            parent_id=base_class,
        )
        self._ontology_items.append(item)
        return item

    async def create_relationship(
        self,
        name: str,
        description: str | None,
        base_property: str | None,
    ) -> OntologyItemData:
        item = OntologyItemData(
            id=f"rel-{int(datetime.now().timestamp() * 1000)}",
            name=name,
            type="relationship",
            description=description,
            parent_id=base_property,
        )
        self._ontology_items.append(item)
        return item

    async def delete_item(self, item_id: str) -> None:
        self._ontology_items = [i for i in self._ontology_items if i.id != item_id]

    async def import_ontology(self, content: str, filename: str) -> ReferenceOntologyData:
        try:
            return _parse_ttl(content, filename)
        except Exception as exc:
            raise OntologyParseError("Failed to parse ontology file") from exc

    async def export_ontology_file(self, ontology_path: str) -> Path:
        path = Path(ontology_path)
        if not path.exists() or not path.is_file():
            from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
                OntologyFileNotFoundError,
            )

            raise OntologyFileNotFoundError("Ontology file does not exist")
        return path

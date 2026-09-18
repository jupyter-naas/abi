"""BFO bucket resolution aligned with Nexus ontology overview (service.py).

Nexus keeps a module-only graph for queries and an imports-enriched graph for
``bfo_parent_iri``. This module mirrors ``_find_bfo_ancestor`` and the ABI
bucket-root aliases so personnel classes resolve the same way.
"""

from __future__ import annotations

from pathlib import Path

import naas_abi
from rdflib import Graph
from rdflib.query import ResultRow

from naas_abi_marketplace.domains.personnel.paths import ONTOLOGIES_DIR

_ABI_NS = "http://ontology.naas.ai/abi/"
_BFO_NS = "http://purl.obolibrary.org/obo/"

_BFO_BUCKET_ROOT_IRIS: tuple[str, ...] = (
    f"{_BFO_NS}BFO_0000040",  # Material Entity (WHO)
    f"{_BFO_NS}BFO_0000015",  # Process (WHAT)
    f"{_BFO_NS}BFO_0000008",  # Temporal Region (WHEN)
    f"{_BFO_NS}BFO_0000029",  # Site (WHERE)
    f"{_BFO_NS}BFO_0000031",  # GDC (HOW WE KNOW)
    f"{_BFO_NS}BFO_0000019",  # Quality (HOW IT IS)
    f"{_BFO_NS}BFO_0000017",  # Realizable (WHY)
)

_BFO_BUCKET_ROOTS = " ".join(f"<{iri}>" for iri in _BFO_BUCKET_ROOT_IRIS)

# ABI equivalents: rdfs:subClassOf often skips the bucket-root IRI (see Nexus comments).
_ABI_TO_BFO_BUCKET_ROOT: dict[str, str] = {
    f"{_ABI_NS}{abi_name}": f"{_BFO_NS}{bfo_id}"
    for abi_name, bfo_id in (
        ("MaterialEntity", "BFO_0000040"),
        ("Site", "BFO_0000029"),
        ("GenericallyDependentContinuant", "BFO_0000031"),
        ("Quality", "BFO_0000019"),
        ("Role", "BFO_0000017"),
        ("Disposition", "BFO_0000017"),
        ("Process", "BFO_0000015"),
        ("TemporalRegion", "BFO_0000008"),
        ("TemporalInstant", "BFO_0000008"),
    )
}
_ABI_BUCKET_VALUES = " ".join(f"<{iri}>" for iri in _ABI_TO_BFO_BUCKET_ROOT)

_BFO_IRI_TO_COCKPIT_TYPE: dict[str, str] = {
    f"{_BFO_NS}BFO_0000040": "Material Entity",
    f"{_BFO_NS}BFO_0000015": "Process",
    f"{_BFO_NS}BFO_0000008": "Temporal Region",
    f"{_BFO_NS}BFO_0000029": "Site",
    f"{_BFO_NS}BFO_0000031": "GDC",
    f"{_BFO_NS}BFO_0000019": "Quality",
    f"{_BFO_NS}BFO_0000017": "Realizable",
    f"{_BFO_NS}BFO_0000001": "Entity",
}

_BFO_ENTITY_IRIS = {
    "BFO_0000001",
    f"{_BFO_NS}BFO_0000001",
}

_ABI_IMPORTS_DIR = Path(naas_abi.__file__).resolve().parent / "ontologies" / "imports"
_ABI_ONTOLOGY_PATH = (
    Path(naas_abi.__file__).resolve().parent / "ontologies" / "modules" / "ABIOntology.ttl"
)

# Bundled imports referenced by PersonnelOntology / ABIOntology (same as Nexus _IMPORT_URI_TO_LOCAL).
_BUCKET_INFERENCE_TTL_PATHS: tuple[Path, ...] = (
    _ABI_ONTOLOGY_PATH,
    _ABI_IMPORTS_DIR / "top-level" / "bfo-core.ttl",
    _ABI_IMPORTS_DIR / "mid-level" / "AgentOntology.ttl",
    _ABI_IMPORTS_DIR / "mid-level" / "QualityOntology.ttl",
    _ABI_IMPORTS_DIR / "mid-level" / "InformationEntityOntology.ttl",
    _ABI_IMPORTS_DIR / "mid-level" / "EventOntology.ttl",
    _ABI_IMPORTS_DIR / "mid-level" / "ExtendedRelationOntology.ttl",
)


def _is_bfo_entity_iri(iri: str | None) -> bool:
    if not iri:
        return False
    if iri in _BFO_ENTITY_IRIS:
        return True
    return iri.rstrip("/") in _BFO_ENTITY_IRIS


def find_bfo_bucket_root_iri(graph: Graph, class_iri: str) -> str | None:
    """Walk rdfs:subClassOf+ to the nearest BFO bucket root (Nexus ``_find_bfo_ancestor``)."""
    if _is_bfo_entity_iri(class_iri):
        return f"{_BFO_NS}BFO_0000001"
    if f"<{class_iri}>" in _BFO_BUCKET_ROOTS:
        return class_iri
    if class_iri in _ABI_TO_BFO_BUCKET_ROOT:
        return _ABI_TO_BFO_BUCKET_ROOT[class_iri]

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
            return _ABI_TO_BFO_BUCKET_ROOT.get(ancestor_iri, ancestor_iri)
    return None


def cockpit_bucket_type(bfo_root_iri: str | None) -> str:
    if not bfo_root_iri:
        return "Unknown"
    return _BFO_IRI_TO_COCKPIT_TYPE.get(bfo_root_iri, "Unknown")


_PERSONNEL_ONTOLOGY_PATHS: tuple[Path, ...] = (
    ONTOLOGIES_DIR / "modules" / "PersonnelOntology.ttl",
    ONTOLOGIES_DIR / "processes" / "ActOfWorkingProcess.ttl",
    ONTOLOGIES_DIR / "processes" / "ActOfStudyingProcess.ttl",
)


def load_bucket_inference_graph() -> Graph:
    """Personnel module graph plus import closure used only for bucket ancestry."""
    graph = Graph()
    seen: set[str] = set()

    def merge_path(path: Path) -> None:
        key = str(path.resolve())
        if key in seen or not path.is_file():
            return
        seen.add(key)
        graph.parse(path, format="turtle")

    for path in _PERSONNEL_ONTOLOGY_PATHS:
        merge_path(path)
    for path in _BUCKET_INFERENCE_TTL_PATHS:
        merge_path(path)
    return graph


def infer_cockpit_bfo_bucket(graph: Graph, class_iri: str) -> str:
    root = find_bfo_bucket_root_iri(graph, class_iri)
    return cockpit_bucket_type(root)

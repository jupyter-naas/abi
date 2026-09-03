"""Load the Periodic Table of Software ontology from TTL files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

PTS_NS = "http://ontology.naas.ai/zen/pts/"
ZEN_NS = "http://ontology.naas.ai/zen/"
ABI_NS = "http://ontology.naas.ai/abi/"

ONTOLOGY_DIR = Path(__file__).resolve().parent
ELEMENTS_DIR = ONTOLOGY_DIR / "elements"
SCHEMA_PATH = ONTOLOGY_DIR / "schema.ttl"
MODULES_PATH = ONTOLOGY_DIR.parent / "modules" / "PeriodicTableOntology.ttl"
ABI_ONTOLOGY = ONTOLOGY_DIR.parent / "modules" / "ABIOntology.ttl"
BFO7_ONTOLOGY = ONTOLOGY_DIR.parent / "modules" / "BFO7BucketsProcessOntology.ttl"
GRAPH_IRI = "http://ontology.naas.ai/graph/abi-periodic-table"
AUTHORING_PATH_MARKER = "/ontologies/periodic_table/"

SECTION_META = {
    "object": {"title": "Objects (Nouns)", "color": "#3b82f6", "range": (1, 35)},
    "property": {"title": "Properties (Attributes)", "color": "#22c55e", "range": (36, 60)},
    "action": {"title": "Actions (Verbs)", "color": "#64748b", "range": (61, 85)},
    "interface": {"title": "Interfaces (Views)", "color": "#eab308", "range": (86, 119)},
    "intelligence": {"title": "Intelligence (AI)", "color": "#ef4444", "range": (101, 108)},
    "rule": {"title": "Rules (Automation)", "color": "#06b6d4", "range": (109, 115)},
}

BFO_BUCKET_LABELS = {
    "material_entity": "Material entity (WHO)",
    "process": "Process (HOW)",
    "site": "Site (WHERE)",
    "information_content_entity": "Information content entity (WHAT)",
    "quality": "Quality (WHICH)",
    "realizable": "Realizable (WHY)",
    "temporal_region": "Temporal region (WHEN)",
}


@dataclass(frozen=True)
class PeriodicElement:
    uri: str
    local_name: str
    label: str
    number: int
    section: str
    bfo_bucket: str
    bfo_bucket_label: str
    bfo_abi_class: str
    bfo_code: str
    definition: str
    alt_label: str | None = None


def is_periodic_table_authoring_path(path: str) -> bool:
    """True for schema/element fragments; those are not catalog ontologies."""
    return AUTHORING_PATH_MARKER in path.replace("\\", "/")


def keep_catalog_ontology_paths(paths: list[str]) -> list[str]:
    """Drop authoring fragments so only ontologies/modules/*.ttl stay registered."""
    return [path for path in paths if not is_periodic_table_authoring_path(path)]


def load_periodic_table_catalog() -> Graph:
    """Parse the canonical modules ontology, or schema + element fragments."""
    g = Graph()
    if MODULES_PATH.is_file():
        g.parse(str(MODULES_PATH), format="turtle")
        return g
    if SCHEMA_PATH.is_file():
        g.parse(str(SCHEMA_PATH), format="turtle")
    if ELEMENTS_DIR.is_dir():
        for fname in sorted(ELEMENTS_DIR.glob("*.ttl")):
            g.parse(str(fname), format="turtle")
    return g


def load_periodic_table_graph() -> Graph:
    """Parse the catalog plus BFO7/ABI when present (for labels and bucket IRIs)."""
    g = load_periodic_table_catalog()
    if BFO7_ONTOLOGY.is_file():
        g.parse(str(BFO7_ONTOLOGY), format="turtle")
    if ABI_ONTOLOGY.is_file():
        g.parse(str(ABI_ONTOLOGY), format="turtle")
    return g


def label_for(g: Graph, uri: str | URIRef) -> str:
    """Human-readable label: rdfs:label from BFO7B/ABI, else local name."""
    ref = URIRef(uri) if isinstance(uri, str) else uri
    label = g.value(ref, RDFS.label)
    if label:
        return str(label)
    uri_str = str(ref)
    for prefix in (
        PTS_NS,
        ZEN_NS,
        ABI_NS,
        "http://purl.obolibrary.org/obo/",
        "https://www.commoncoreontologies.org/",
    ):
        if uri_str.startswith(prefix):
            return uri_str[len(prefix) :]
    return uri_str.rsplit("/", 1)[-1]


def extract_elements(g: Graph | None = None) -> list[PeriodicElement]:
    """Return all pts:SoftwareElement subclasses sorted by element number."""
    graph = g or load_periodic_table_graph()
    elements: list[PeriodicElement] = []

    for cls in graph.subjects(RDF.type, URIRef("http://www.w3.org/2002/07/owl#Class")):
        cls_str = str(cls)
        if not cls_str.startswith(PTS_NS):
            continue
        if (cls_str.split("/")[-1]).startswith("Software"):
            continue

        number = graph.value(cls, URIRef(f"{PTS_NS}elementNumber"))
        section = graph.value(cls, URIRef(f"{PTS_NS}section"))
        bfo_bucket = graph.value(cls, URIRef(f"{PTS_NS}bfoBucket"))
        bfo_bucket_label = graph.value(cls, URIRef(f"{PTS_NS}bfoBucketLabel"))
        bfo_abi = graph.value(cls, URIRef(f"{ZEN_NS}mapsToBFOBucket"))
        bfo_code = graph.value(cls, URIRef(f"{ZEN_NS}mapsToBFOCode"))
        if number is None or section is None:
            continue

        label = graph.value(cls, RDFS.label)
        definition = graph.value(cls, SKOS.definition)
        alt = graph.value(cls, SKOS.altLabel)

        elements.append(
            PeriodicElement(
                uri=cls_str,
                local_name=cls_str.rsplit("/", 1)[-1],
                label=str(label or cls_str.rsplit("/", 1)[-1]),
                number=int(number),
                section=str(section),
                bfo_bucket=str(bfo_bucket or ""),
                bfo_bucket_label=str(
                    bfo_bucket_label or BFO_BUCKET_LABELS.get(str(bfo_bucket or ""), "")
                ),
                bfo_abi_class=str(bfo_abi or ""),
                bfo_code=str(bfo_code or ""),
                definition=str(definition or ""),
                alt_label=str(alt) if alt else None,
            )
        )

    return sorted(elements, key=lambda e: e.number)


def insert_into_triple_store(ts, graph: Graph | None = None) -> None:
    """Load the catalog into the abi-periodic-table named graph."""
    combined = graph or load_periodic_table_catalog()
    graph_uri = URIRef(GRAPH_IRI)
    try:
        ts.clear_graph(graph_uri)
    except Exception:
        pass
    ts.insert(combined, graph_name=graph_uri)

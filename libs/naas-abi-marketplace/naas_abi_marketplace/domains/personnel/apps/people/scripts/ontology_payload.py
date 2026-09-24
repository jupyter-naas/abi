"""Personnel ontology bundle for the People Search schema viewer."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from naas_abi_core.utils.validate_bfo_ontology import _collect_all_restrictions
from naas_abi_marketplace.domains.personnel.apps.people.scripts.bfo_bucket_resolution import (
    CCO_MID_LEVEL_DIR,
    infer_cockpit_bfo_bucket,
    load_bucket_inference_graph,
)
from naas_abi_marketplace.domains.personnel.paths import ONTOLOGIES_DIR
from rdflib import OWL, RDF, RDFS, Graph, URIRef
from rdflib.namespace import SKOS

PERSONNEL_NS = "http://ontology.naas.ai/personnel/"
ABI_NS = "http://ontology.naas.ai/abi/"

# The module first, then every process slice: a new slice is picked up by being
# filed under ontologies/processes, not by being remembered here.
ONTOLOGY_SOURCES: tuple[tuple[str, Path], ...] = (
    ("PersonnelOntology.ttl", ONTOLOGIES_DIR / "modules" / "PersonnelOntology.ttl"),
    *(
        (path.name, path)
        for path in sorted((ONTOLOGIES_DIR / "processes").glob("*.ttl"))
    ),
)

CCO_NS = "https://www.commoncoreontologies.org/"

# CCO classes the personnel ontology builds on and the viewer shows as classes of
# their own: the facilities an act occurs in, and the educational organization
# that runs one. Everything else of CCO stays out, as before.
_FACILITY_ONTOLOGY = CCO_MID_LEVEL_DIR / "FacilityOntology.ttl"
_LABEL_SOURCES = tuple(
    CCO_MID_LEVEL_DIR / name
    for name in ("FacilityOntology.ttl", "ArtifactOntology.ttl", "AgentOntology.ttl")
)
_EDUCATIONAL_ORGANIZATION = URIRef(f"{CCO_NS}ont00000564")


@lru_cache(maxsize=1)
def _facility_classes() -> frozenset[URIRef]:
    facilities = Graph().parse(_FACILITY_ONTOLOGY, format="turtle")
    return frozenset(
        s
        for s in facilities.subjects(RDF.type, OWL.Class)
        if isinstance(s, URIRef) and str(s).startswith(CCO_NS)
    ) | {_EDUCATIONAL_ORGANIZATION}


def _in_scope(uri: URIRef) -> bool:
    text = str(uri)
    return (
        text.startswith(PERSONNEL_NS)
        or text.startswith(ABI_NS)
        or uri in _facility_classes()
    )


def _qname(graph: Graph, uri: URIRef) -> str:
    try:
        return graph.namespace_manager.qname(uri)
    except Exception:  # noqa: BLE001
        return str(uri)


def _label(graph: Graph, uri: URIRef) -> str:
    value = graph.value(uri, RDFS.label)
    if value is not None:
        return str(value)
    return _qname(graph, uri).split(":")[-1]


def _text_value(graph: Graph, uri: URIRef, predicate: URIRef) -> str | None:
    value = graph.value(uri, predicate)
    if value is None:
        return None
    return str(value)


def _add_imported_classes(graph: Graph) -> None:
    """State, as classes, the CCO facility classes the personnel files build on.

    The files name them by IRI only (``occursIn some cco:ont00000468``); their
    labels live in the CCO imports. Each one used is stated here with its label,
    definition and its facility parents, so the viewer can name it and show where
    it sits, and so the merged document says what it is.
    """
    known = _facility_classes()
    used: set[URIRef] = set()
    for triple in graph:
        used.update(term for term in triple if term in known)
    labels = Graph()
    for path in _LABEL_SOURCES:
        labels.parse(path, format="turtle")

    pending = sorted(used)
    stated: set[URIRef] = set()
    while pending:
        cls = pending.pop()
        if cls in stated:
            continue
        stated.add(cls)
        graph.add((cls, RDF.type, OWL.Class))
        for predicate in (RDFS.label, SKOS.definition):
            for value in labels.objects(cls, predicate):
                graph.add((cls, predicate, value))
        for parent in labels.objects(cls, RDFS.subClassOf):
            if isinstance(parent, URIRef) and parent in known:
                graph.add((cls, RDFS.subClassOf, parent))
                pending.append(parent)


def load_personnel_schema_graph() -> Graph:
    graph = Graph()
    for _, path in ONTOLOGY_SOURCES:
        graph.parse(path, format="turtle")
    _add_imported_classes(graph)
    return graph


PREFIXES = {
    "personnel": PERSONNEL_NS,
    "abi": ABI_NS,
    "cco": "https://www.commoncoreontologies.org/",
    "bfo": "http://purl.obolibrary.org/obo/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "dc": "http://purl.org/dc/terms/",
    "dc11": "http://purl.org/dc/elements/1.1/",
}


def merged_turtle(graph: Graph) -> str:
    """The module and every process slice as one document.

    The slices restate classes of the module to add their own restrictions, so
    the files taken one after another say some things twice and repeat every
    prefix. Read as one graph they are said once, and a class is one block.
    """
    merged = Graph()
    for prefix, namespace in PREFIXES.items():
        merged.bind(prefix, namespace)
    for triple in graph:
        merged.add(triple)
    return merged.serialize(format="turtle")


def _ttl_bundle(graph: Graph) -> tuple[list[dict[str, str]], str]:
    sources: list[dict[str, str]] = []
    for name, path in ONTOLOGY_SOURCES:
        text = path.read_text(encoding="utf-8")
        sources.append({"name": name, "path": str(path.relative_to(ONTOLOGIES_DIR.parent)), "text": text})
    return sources, merged_turtle(graph)


def _class_uris(graph: Graph) -> list[URIRef]:
    uris: set[URIRef] = set()
    for subject in graph.subjects(RDF.type, OWL.Class):
        if isinstance(subject, URIRef) and _in_scope(subject):
            uris.add(subject)

    def absorb(uri: URIRef) -> None:
        if _in_scope(uri):
            uris.add(uri)

    changed = True
    while changed:
        changed = False
        snapshot = list(uris)
        for class_uri in snapshot:
            for parent in graph.objects(class_uri, RDFS.subClassOf):
                if isinstance(parent, URIRef):
                    before = len(uris)
                    absorb(parent)
                    if len(uris) > before:
                        changed = True
            for item in _collect_all_restrictions(graph, class_uri):
                filler = item.get("filler")
                if isinstance(filler, URIRef):
                    before = len(uris)
                    absorb(filler)
                    if len(uris) > before:
                        changed = True
        for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
            if not isinstance(prop, URIRef) or not _in_scope(prop):
                continue
            for domain in graph.objects(prop, RDFS.domain):
                if isinstance(domain, URIRef):
                    absorb(domain)
            for range_uri in graph.objects(prop, RDFS.range):
                if isinstance(range_uri, URIRef):
                    absorb(range_uri)

    return sorted(uris, key=lambda uri: _label(graph, uri).lower())


def _object_properties(graph: Graph) -> list[URIRef]:
    props = [
        s for s in graph.subjects(RDF.type, OWL.ObjectProperty) if isinstance(s, URIRef)
    ]
    return sorted([p for p in props if _in_scope(p)], key=lambda uri: _label(graph, uri).lower())


def _datatype_properties(graph: Graph) -> list[URIRef]:
    props = [
        s for s in graph.subjects(RDF.type, OWL.DatatypeProperty) if isinstance(s, URIRef)
    ]
    return sorted([p for p in props if _in_scope(p)], key=lambda uri: _label(graph, uri).lower())


_STANDARD_ANNOTATION_PREDICATES: tuple[URIRef, ...] = (
    RDFS.label,
    RDFS.comment,
    RDFS.seeAlso,
    SKOS.definition,
    SKOS.example,
    SKOS.altLabel,
    SKOS.prefLabel,
    SKOS.note,
)


def _annotation_properties(graph: Graph) -> list[URIRef]:
    found: set[URIRef] = set()
    for prop in graph.subjects(RDF.type, OWL.AnnotationProperty):
        if isinstance(prop, URIRef) and _in_scope(prop):
            found.add(prop)
    for pred in _STANDARD_ANNOTATION_PREDICATES:
        for subject in graph.subjects(pred, None):
            if isinstance(subject, URIRef) and _in_scope(subject):
                found.add(pred)
                break
    return sorted(found, key=lambda uri: _label(graph, uri).lower())


def _restriction_count(graph: Graph, class_uris: list[URIRef]) -> int:
    total = 0
    for class_uri in class_uris:
        for item in _collect_all_restrictions(graph, class_uri):
            if isinstance(item.get("on_prop"), URIRef):
                total += 1
    return total


def _superclasses(graph: Graph, class_uri: URIRef) -> list[str]:
    parents: list[str] = []
    for parent in graph.objects(class_uri, RDFS.subClassOf):
        if isinstance(parent, URIRef) and _in_scope(parent):
            parents.append(_qname(graph, parent))
    return sorted(set(parents))


def _subclasses(graph: Graph, class_uri: URIRef, known: set[URIRef]) -> list[str]:
    children: list[str] = []
    for child in graph.subjects(RDFS.subClassOf, class_uri):
        if isinstance(child, URIRef) and child in known:
            children.append(_qname(graph, child))
    return sorted(set(children))


def build_ontology_payload() -> dict:
    graph = load_personnel_schema_graph()
    bucket_graph = load_bucket_inference_graph()
    sources, display_ttl = _ttl_bundle(graph)
    class_uris = _class_uris(graph)
    known_classes = set(class_uris)
    object_props = _object_properties(graph)
    datatype_props = _datatype_properties(graph)
    annotation_props = _annotation_properties(graph)

    classes: dict[str, dict] = {}
    for class_uri in class_uris:
        iri = str(class_uri)
        qname = _qname(graph, class_uri)
        restrictions = []
        for item in _collect_all_restrictions(graph, class_uri):
            prop = item.get("on_prop")
            filler = item.get("filler")
            if not isinstance(prop, URIRef):
                continue
            restrictions.append(
                {
                    "property": _qname(graph, prop),
                    "property_label": _label(graph, prop),
                    "quantifier": item.get("quantifier") or "restriction",
                    "filler": _qname(graph, filler) if isinstance(filler, URIRef) else None,
                    "filler_label": _label(graph, filler) if isinstance(filler, URIRef) else None,
                }
            )

        domain_props: list[dict[str, str]] = []
        range_props: list[dict[str, str]] = []
        for prop in object_props:
            domains = [d for d in graph.objects(prop, RDFS.domain) if isinstance(d, URIRef)]
            ranges = [r for r in graph.objects(prop, RDFS.range) if isinstance(r, URIRef)]
            if class_uri in domains:
                domain_props.append(
                    {"property": _qname(graph, prop), "label": _label(graph, prop)}
                )
            if class_uri in ranges:
                range_props.append(
                    {"property": _qname(graph, prop), "label": _label(graph, prop)}
                )

        datatype_on_class: list[dict[str, str]] = []
        for prop in datatype_props:
            domains = [d for d in graph.objects(prop, RDFS.domain) if isinstance(d, URIRef)]
            if class_uri in domains:
                ranges = [r for r in graph.objects(prop, RDFS.range) if r is not None]
                datatype_on_class.append(
                    {
                        "property": _qname(graph, prop),
                        "label": _label(graph, prop),
                        "range": str(ranges[0]) if ranges else None,
                    }
                )

        bfo_bucket = infer_cockpit_bfo_bucket(bucket_graph, str(class_uri))

        classes[iri] = {
            "id": qname,
            "iri": iri,
            "label": _label(graph, class_uri),
            "bfo_bucket": bfo_bucket,
            "definition": _text_value(graph, class_uri, SKOS.definition),
            "comment": _text_value(graph, class_uri, RDFS.comment),
            "superclasses": _superclasses(graph, class_uri),
            "subclasses": _subclasses(graph, class_uri, known_classes),
            "restrictions": restrictions,
            "object_properties_domain": domain_props,
            "object_properties_range": range_props,
            "datatype_properties": datatype_on_class,
        }

    nodes = [
        {
            "id": classes[str(uri)]["id"],
            "iri": str(uri),
            "label": classes[str(uri)]["label"],
            "kind": "class",
            "bfo_bucket": classes[str(uri)]["bfo_bucket"],
        }
        for uri in class_uris
    ]
    node_ids = {node["id"] for node in nodes}
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str, str]] = set()

    def add_edge(
        source: str,
        target: str,
        kind: str,
        label: str = "",
    ) -> None:
        if source not in node_ids or target not in node_ids:
            return
        key = (source, target, kind, label)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"from": source, "to": target, "kind": kind, "label": label})

    for class_uri in class_uris:
        source = _qname(graph, class_uri)
        for parent in graph.objects(class_uri, RDFS.subClassOf):
            if isinstance(parent, URIRef) and parent in known_classes:
                add_edge(source, _qname(graph, parent), "subClassOf", "subClassOf")

        for item in _collect_all_restrictions(graph, class_uri):
            if item.get("cls") != class_uri:
                continue
            prop = item.get("on_prop")
            filler = item.get("filler")
            if not isinstance(prop, URIRef) or not isinstance(filler, URIRef):
                continue
            if filler not in known_classes:
                continue
            quant = str(item.get("quantifier") or "on")
            add_edge(
                source,
                _qname(graph, filler),
                "restriction",
                f"{_qname(graph, prop)} ({quant})",
            )

    for prop in object_props:
        domains = [d for d in graph.objects(prop, RDFS.domain) if isinstance(d, URIRef)]
        ranges = [r for r in graph.objects(prop, RDFS.range) if isinstance(r, URIRef)]
        prop_label = _label(graph, prop)
        for domain in domains:
            for range_uri in ranges:
                if domain in known_classes and range_uri in known_classes:
                    add_edge(
                        _qname(graph, domain),
                        _qname(graph, range_uri),
                        "objectProperty",
                        prop_label,
                    )

    ontology_iri = graph.value(None, RDF.type, OWL.Ontology)
    title = "Personnel Ontology"
    if isinstance(ontology_iri, URIRef):
        title = _text_value(graph, ontology_iri, RDFS.label) or title

    return {
        "title": title,
        "sources": sources,
        "display_ttl": display_ttl,
        "stats": {
            "classes": len(class_uris),
            "restrictions": _restriction_count(graph, class_uris),
            "object_properties": len(object_props),
            "datatype_properties": len(datatype_props),
            "annotation_properties": len(annotation_props),
        },
        "graph": {"nodes": nodes, "edges": edges},
        "classes": classes,
    }

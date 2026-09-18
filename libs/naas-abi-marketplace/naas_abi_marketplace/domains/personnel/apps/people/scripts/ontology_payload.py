"""Personnel ontology bundle for the People Search schema viewer."""

from __future__ import annotations

from pathlib import Path

from naas_abi_core.utils.validate_bfo_ontology import _collect_all_restrictions
from naas_abi_marketplace.domains.personnel.apps.people.scripts.bfo_bucket_resolution import (
    infer_cockpit_bfo_bucket,
    load_bucket_inference_graph,
)
from naas_abi_marketplace.domains.personnel.paths import ONTOLOGIES_DIR
from rdflib import OWL, RDF, RDFS, Graph, URIRef
from rdflib.namespace import SKOS

PERSONNEL_NS = "http://ontology.naas.ai/personnel/"
ABI_NS = "http://ontology.naas.ai/abi/"

ONTOLOGY_SOURCES: tuple[tuple[str, Path], ...] = (
    ("PersonnelOntology.ttl", ONTOLOGIES_DIR / "modules" / "PersonnelOntology.ttl"),
    ("ActOfWorkingProcess.ttl", ONTOLOGIES_DIR / "processes" / "ActOfWorkingProcess.ttl"),
    ("ActOfStudyingProcess.ttl", ONTOLOGIES_DIR / "processes" / "ActOfStudyingProcess.ttl"),
)

def _in_scope(uri: URIRef) -> bool:
    text = str(uri)
    return text.startswith(PERSONNEL_NS) or text.startswith(ABI_NS)


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


def load_personnel_schema_graph() -> Graph:
    graph = Graph()
    for _, path in ONTOLOGY_SOURCES:
        graph.parse(path, format="turtle")
    return graph


def _ttl_bundle() -> tuple[list[dict[str, str]], str]:
    sources: list[dict[str, str]] = []
    parts: list[str] = []
    for name, path in ONTOLOGY_SOURCES:
        text = path.read_text(encoding="utf-8")
        sources.append({"name": name, "path": str(path.relative_to(ONTOLOGIES_DIR.parent)), "text": text})
        parts.append(f"# ── {name} ──\n{text.strip()}\n")
    return sources, "\n\n".join(parts)


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
    sources, display_ttl = _ttl_bundle()
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

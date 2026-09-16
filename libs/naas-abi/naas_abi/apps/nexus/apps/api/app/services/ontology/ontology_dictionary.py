"""Dictionary projection of explicitly supplied, workspace-visible graphs."""

from collections.abc import Iterable
from typing import Any

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DC, DCAT, DCTERMS, OWL, RDF, RDFS, SKOS


def build_workspace_dictionary(
    sources: Iterable[tuple[dict[str, str], Graph]],
) -> list[dict[str, Any]]:
    """Merge declarations by kind and IRI, retaining every visible provenance.

    This function never resolves imports or opens files. The caller supplies only
    graphs admitted by the same catalog policy as the ontology file sidebar.
    """
    sources = list(sources)
    combined = Graph()
    for _, graph in sources:
        combined += graph

    def literals(graph: Graph, subject: URIRef, predicate: URIRef) -> list[str]:
        values = sorted(
            (v for v in graph.objects(subject, predicate) if isinstance(v, Literal)),
            key=lambda v: (v.language not in ("en", None), str(v)),
        )
        return list(dict.fromkeys(str(v) for v in values))

    def label(iri: URIRef) -> str:
        values = literals(combined, iri, RDFS.label)
        return values[0] if values else str(iri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]

    def links(iri: URIRef, predicate: URIRef) -> list[dict[str, Any]]:
        return [
            {"id": str(value), "name": label(value), "sources": [
                source for source, graph in sources if (iri, predicate, value) in graph
            ]}
            for value in sorted(set(combined.objects(iri, predicate)), key=str)
            if isinstance(value, URIRef)
        ]

    def annotation_values(iri: URIRef, *predicates: URIRef) -> list[str]:
        values = set()
        for predicate in predicates:
            for value in combined.objects(iri, predicate):
                if isinstance(value, Literal):
                    values.add(str(value))
                elif isinstance(value, URIRef):
                    values.add(label(value))
        return sorted(values)

    def process_ledger(iri: URIRef) -> dict[str, Any] | None:
        # Original business buckets are provenance, not additional BFO assertions.
        namespace = "http://ontology.naas.ai/abi/"
        buckets = {}
        for bucket in ("WHO", "WHERE", "WHEN", "HOWITIS", "WHY", "HOWWEKNOW"):
            predicate = URIRef(namespace + "ledger" + bucket)
            entries = []
            for value in literals(combined, iri, predicate):
                provenance = [source for source, graph in sources
                              if value in literals(graph, iri, predicate)]
                entries.append({"value": value, "sources": provenance})
            buckets[bucket] = entries
        if not any(buckets.values()):
            return None
        return {"code": next(iter(literals(combined, iri, URIRef(namespace + "ledgerCode"))), None),
                "buckets": buckets,
                "status": literals(combined, iri, URIRef(namespace + "modelingStatus"))}

    kinds = {
        OWL.Class: "entity", RDFS.Class: "entity",
        OWL.ObjectProperty: "relationship", OWL.DatatypeProperty: "attribute",
        OWL.AnnotationProperty: "annotation", OWL.NamedIndividual: "individual",
    }
    terms: dict[tuple[str, str], dict[str, Any]] = {}
    for source, graph in sources:
        for rdf_type, kind in kinds.items():
            for subject in sorted(set(graph.subjects(RDF.type, rdf_type)), key=str):
                if not isinstance(subject, URIRef):
                    continue
                key = (kind, str(subject))
                if key not in terms:
                    parent_predicate = RDF.type if kind == "individual" else RDFS.subClassOf if kind == "entity" else RDFS.subPropertyOf
                    parents = [parent for parent in links(subject, parent_predicate) if parent["id"] != str(OWL.NamedIndividual)]
                    definitions = literals(combined, subject, SKOS.definition) or literals(combined, subject, RDFS.comment)
                    terms[key] = {
                        "id": str(subject), "name": label(subject), "type": kind,
                        "description": definitions[0] if definitions else None,
                        "definitions": [], "sources": [], "parents": parents,
                        "parent_id": parents[0]["id"] if parents else None,
                        "parent_name": parents[0]["name"] if parents else None,
                        "domain": links(subject, RDFS.domain),
                        "range": links(subject, RDFS.range),
                        "inverse": links(subject, OWL.inverseOf),
                        "equivalents": links(subject, OWL.equivalentClass) if kind == "entity" else [],
                        "systemViewKind": next(iter(literals(combined, subject, URIRef("http://ontology.naas.ai/abi/systemViewKind"))), None) if kind == "entity" else None,
                        "systemViewParents": links(subject, URIRef("http://ontology.naas.ai/abi/systemViewParent")) if kind == "entity" else [],
                        "processLedger": process_ledger(subject) if kind == "entity" else None,
                        "sourceValues": literals(combined, subject, URIRef("http://ontology.naas.ai/abi/sourceValue")),
                        "examples": literals(combined, subject, SKOS.example),
                        "aliases": literals(combined, subject, SKOS.altLabel),
                        "contributors": annotation_values(subject, DCTERMS.contributor, DC.contributor),
                        "contacts": annotation_values(subject, DCAT.contactPoint),
                    }
                term = terms[key]
                if source not in term["sources"]:
                    term["sources"].append(source)
                definitions = literals(graph, subject, SKOS.definition) or literals(graph, subject, RDFS.comment)
                for value in definitions:
                    definition = {"value": value, "source_path": source["path"]}
                    if definition not in term["definitions"]:
                        term["definitions"].append(definition)
    # Preserve explicit relationships and direct subclass restrictions, with file provenance.
    # These describe ontology declarations, never observed process executions.
    object_properties = set(combined.subjects(RDF.type, OWL.ObjectProperty))
    relations_by_subject: dict[str, dict[tuple[str, str, str, str], dict[str, Any]]] = {}
    declared_subjects = {iri for _, iri in terms}
    for source, graph in sources:
        for subject in set(graph.subjects()):
            if not isinstance(subject, URIRef) or str(subject) not in declared_subjects:
                continue
            relations = relations_by_subject.setdefault(str(subject), {})

            def add_relation(
                prop: URIRef,
                target: URIRef,
                kind: str,
                constraint: str = "",
                *,
                _relations: dict[tuple[str, str, str, str], dict[str, Any]] = relations,
                _source: dict[str, str] = source,
            ) -> None:
                key = (str(prop), str(target), kind, constraint)
                if key not in _relations:
                    _relations[key] = {
                        "property": {"id": str(prop), "name": label(prop)},
                        "target": {"id": str(target), "name": label(target)},
                        "kind": kind, "constraint": constraint, "sources": [],
                    }
                if _source not in _relations[key]["sources"]:
                    _relations[key]["sources"].append(_source)

            for prop, target in graph.predicate_objects(subject):
                if prop in object_properties and isinstance(target, URIRef):
                    add_relation(prop, target, "assertion")
            for restriction in graph.objects(subject, RDFS.subClassOf):
                if not isinstance(restriction, BNode) or (restriction, RDF.type, OWL.Restriction) not in graph:
                    continue
                prop = graph.value(restriction, OWL.onProperty)
                if not isinstance(prop, URIRef):
                    continue
                for predicate, constraint in ((OWL.someValuesFrom, "some"), (OWL.allValuesFrom, "only"), (OWL.hasValue, "value")):
                    for target in graph.objects(restriction, predicate):
                        if isinstance(target, URIRef):
                            add_relation(prop, target, "restriction", constraint)
    for term in terms.values():
        term["relations"] = sorted(
            relations_by_subject.get(term["id"], {}).values(),
            key=lambda relation: (relation["property"]["id"], relation["target"]["id"], relation["constraint"]),
        )
    return sorted(terms.values(), key=lambda term: (term["name"].casefold(), term["id"], term["type"]))

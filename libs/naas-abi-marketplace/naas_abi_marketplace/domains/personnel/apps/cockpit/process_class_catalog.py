"""Process-scoped class labels derived from personnel ontology restrictions."""

from __future__ import annotations

from pathlib import Path

from naas_abi_core.utils.validate_bfo_ontology import _collect_all_restrictions
from naas_abi_marketplace.domains.personnel.paths import ONTOLOGIES_DIR, PERSONNEL_ROOT
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

PERSONNEL_NS = "http://ontology.naas.ai/personnel/"
ABI_NS = "http://ontology.naas.ai/abi/"

PROCESS_SPECS: tuple[dict[str, str | Path | tuple[Path, ...]], ...] = (
    {
        "process_label": "Act of Working",
        "process_class": f"{PERSONNEL_NS}ActOfWorking",
        "process_ontology": ONTOLOGIES_DIR / "processes" / "ActOfWorkingProcess.ttl",
        "support_ontologies": (),
    },
    {
        "process_label": "Act of Studying",
        "process_class": f"{PERSONNEL_NS}ActOfStudying",
        "process_ontology": ONTOLOGIES_DIR / "processes" / "ActOfStudyingProcess.ttl",
        # ProfileDocument and Skill are declared in the working slice.
        "support_ontologies": (ONTOLOGIES_DIR / "processes" / "ActOfWorkingProcess.ttl",),
    },
)

SHARED_ONTOLOGY = ONTOLOGIES_DIR / "modules" / "PersonnelOntology.ttl"

EXCLUDED_CLASS_LABELS = frozenset({"Person", "Act of Working", "Act of Studying"})

# ABI classes referenced by personnel restrictions but not always labelled in slice TTLs.
_ABI_CLASS_LABELS: dict[str, str] = {
    f"{ABI_NS}Person": "Person",
    f"{ABI_NS}Organization": "Organization",
    f"{ABI_NS}Site": "Site",
    f"{ABI_NS}TemporalRegion": "Temporal Region",
    f"{ABI_NS}TemporalInstant": "Temporal Instant",
}

# Structural companions documented in process slice comments (region bounds).
_COMPANION_CLASS_LABELS: dict[str, tuple[str, ...]] = {
    "Temporal Region": ("Temporal Instant",),
}


def _class_label(graph: Graph, class_uri: URIRef) -> str | None:
    label = graph.value(class_uri, RDFS.label)
    if label is not None:
        return str(label)
    return _ABI_CLASS_LABELS.get(str(class_uri))


def _declared_classes(graph: Graph) -> set[URIRef]:
    return {subject for subject in graph.subjects(RDF.type, OWL.Class) if isinstance(subject, URIRef)}


def _is_catalog_class(graph: Graph, class_uri: URIRef) -> bool:
    if (class_uri, RDF.type, OWL.Class) in graph:
        return True
    return str(class_uri) in _ABI_CLASS_LABELS


def _is_relevant_uri(class_uri: URIRef) -> bool:
    text = str(class_uri)
    return text.startswith(PERSONNEL_NS) or text.startswith(ABI_NS)


def _restriction_fillers(graph: Graph, class_uri: URIRef) -> set[URIRef]:
    fillers: set[URIRef] = set()
    for restriction in _collect_all_restrictions(graph, class_uri):
        filler = restriction.get("filler")
        if isinstance(filler, URIRef):
            fillers.add(filler)
    return fillers


def _classes_referencing_process(graph: Graph, process_class: URIRef) -> set[URIRef]:
    referenced: set[URIRef] = set()
    for subject in graph.subjects(RDF.type, OWL.Class):
        if not isinstance(subject, URIRef):
            continue
        for filler in _restriction_fillers(graph, subject):
            if filler == process_class:
                referenced.add(subject)
                break
    return referenced


def _collect_process_class_uris(
    graph: Graph,
    process_class: URIRef,
    process_slice: Graph,
) -> set[URIRef]:
    """Collect continuant classes allowed for a process slice."""
    discovered: set[URIRef] = set()
    queue: list[URIRef] = []

    def _enqueue(class_uri: URIRef) -> None:
        if class_uri == process_class or class_uri in discovered:
            return
        if not _is_relevant_uri(class_uri) or not _is_catalog_class(graph, class_uri):
            return
        discovered.add(class_uri)
        queue.append(class_uri)

    for filler in _restriction_fillers(graph, process_class):
        _enqueue(filler)

    for declared in _declared_classes(process_slice):
        _enqueue(declared)

    for referenced in _classes_referencing_process(graph, process_class):
        _enqueue(referenced)

    while queue:
        current = queue.pop(0)
        for filler in _restriction_fillers(graph, current):
            _enqueue(filler)

    return discovered


def _labels_for_process(graph: Graph, process_class: URIRef, process_slice: Graph) -> list[str]:
    labels: set[str] = set()
    for class_uri in _collect_process_class_uris(graph, process_class, process_slice):
        label = _class_label(graph, class_uri)
        if not label or label in EXCLUDED_CLASS_LABELS:
            continue
        labels.add(label)
        for companion in _COMPANION_CLASS_LABELS.get(label, ()):
            if companion not in EXCLUDED_CLASS_LABELS:
                labels.add(companion)
    return sorted(labels)


def build_process_class_catalog(
    *,
    personnel_root: Path = PERSONNEL_ROOT,
) -> dict[str, dict[str, list[str]]]:
    """Return allowed non-process class labels keyed by process class label."""
    shared = Graph()
    shared.parse(SHARED_ONTOLOGY)

    catalog: dict[str, dict[str, list[str]]] = {}
    for spec in PROCESS_SPECS:
        process_slice = Graph()
        process_slice.parse(spec["process_ontology"])
        graph = Graph()
        graph += shared
        graph += process_slice
        for support_path in spec.get("support_ontologies", ()):
            graph.parse(support_path)
        process_class = URIRef(str(spec["process_class"]))
        class_labels = _labels_for_process(graph, process_class, process_slice)
        catalog[str(spec["process_label"])] = {
            "processClass": str(spec["process_class"]),
            "classLabels": class_labels,
        }
    return catalog

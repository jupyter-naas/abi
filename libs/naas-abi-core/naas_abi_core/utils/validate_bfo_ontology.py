"""
validate_bfo_ontology.py
------------------------
Validates a Turtle (.ttl) ontology file against the BFO 7 Buckets framework.

Usage
-----
    python validate_bfo_ontology.py path/to/ontology.ttl [--raise-error]

Arguments
---------
    ttl_path       Path to the Turtle file to validate.
    --raise-error  Stop on the first error found and raise a ValueError.
                   Omit to collect all errors and print a full JSON report.

Output
------
    A JSON report printed to stdout with the following top-level keys:
        summary   : counts by severity and category
        errors    : list of error dicts (severity ERROR)
        warnings  : list of error dicts (severity WARNING)
        info      : list of info dicts (severity INFO)
        imports   : list of import status dicts (iri, status, message)

Each issue dict contains:
        severity  : "ERROR" | "WARNING" | "INFO"
        category  : one of the check categories below
        subject   : the IRI or label of the element under scrutiny
        message   : human-readable description of the problem
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Any

try:
    from rdflib import OWL, RDF, RDFS, BNode, Graph, Namespace, URIRef
    from rdflib.namespace import SKOS
except ImportError:
    print(
        "ERROR: rdflib is required.  Install it with:  pip install rdflib",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# BFO 7 Buckets — canonical root IRIs
# ---------------------------------------------------------------------------
BFO = Namespace("http://purl.obolibrary.org/obo/")

BUCKET_ROOTS: dict[str, URIRef] = {
    "WHAT (process)": BFO["BFO_0000015"],
    "WHEN (temporal region)": BFO["BFO_0000008"],
    "WHO (material entity)": BFO["BFO_0000040"],
    "WHERE (site)": BFO["BFO_0000029"],
    "HOW WE KNOW (gen. dep. continuant)": BFO["BFO_0000031"],
    "HOW IT IS (quality)": BFO["BFO_0000019"],
    "WHY/role (role)": BFO["BFO_0000023"],
    "WHY/disposition (disposition)": BFO["BFO_0000016"],
}

ALL_BUCKET_ROOTS: set[URIRef] = set(BUCKET_ROOTS.values())

BFO_INHERES_IN = BFO["BFO_0000197"]
BFO_BEARER_OF = BFO["BFO_0000196"]
BFO_HAS_MATERIAL_BASIS = BFO["BFO_0000218"]
BFO_HAS_REALIZATION = BFO["BFO_0000054"]
BFO_REALIZES = BFO["BFO_0000055"]

REQUIRES_INHERES_IN: set[URIRef] = {
    BFO["BFO_0000019"],
    BFO["BFO_0000023"],
    BFO["BFO_0000016"],
}

REQUIRED_ANNOTATIONS: list[tuple[URIRef, str]] = [
    (RDFS.label, "rdfs:label"),
    (SKOS.definition, "skos:definition"),
    (SKOS.example, "skos:example"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _short(iri: Any, g: Graph) -> str:
    if isinstance(iri, BNode):
        return "_:bnode"
    try:
        return g.namespace_manager.qname(iri)
    except Exception:
        s = str(iri)
        return s.split("/")[-1].split("#")[-1]


def _label(iri: Any, g: Graph) -> str:
    if not isinstance(iri, (URIRef, BNode)):
        return str(iri) if iri is not None else "?"
    lbl = g.value(iri, RDFS.label) if isinstance(iri, URIRef) else None
    if lbl:
        return str(lbl)
    return _short(iri, g)


def _all_superclasses(cls: URIRef, g: Graph, visited: set | None = None) -> set[URIRef]:
    if visited is None:
        visited = set()
    if cls in visited:
        return visited
    visited.add(cls)
    for parent in g.objects(cls, RDFS.subClassOf):
        if isinstance(parent, URIRef):
            _all_superclasses(parent, g, visited)
    return visited


def _restriction_properties(g: Graph, cls: URIRef) -> set[URIRef]:
    props: set[URIRef] = set()
    for parent in g.objects(cls, RDFS.subClassOf):
        if isinstance(parent, BNode):
            rdf_type = g.value(parent, RDF.type)
            if rdf_type == OWL.Restriction:
                on_prop = g.value(parent, OWL.onProperty)
                if isinstance(on_prop, URIRef):
                    props.add(on_prop)
    return props


def _restriction_fillers(g: Graph, cls: URIRef) -> set[URIRef]:
    fillers: set[URIRef] = set()
    for parent in g.objects(cls, RDFS.subClassOf):
        if isinstance(parent, BNode):
            rdf_type = g.value(parent, RDF.type)
            if rdf_type == OWL.Restriction:
                for pred in (OWL.allValuesFrom, OWL.someValuesFrom):
                    filler = g.value(parent, pred)
                    if isinstance(filler, URIRef):
                        fillers.add(filler)
    return fillers


def _named_classes(g: Graph) -> list[URIRef]:
    return [s for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)]


def _named_object_properties(g: Graph) -> list[URIRef]:
    return [
        s for s in g.subjects(RDF.type, OWL.ObjectProperty) if isinstance(s, URIRef)
    ]


def _all_properties_used_in_restrictions(g: Graph) -> set[URIRef]:
    return {o for o in g.objects(None, OWL.onProperty) if isinstance(o, URIRef)}


# ---------------------------------------------------------------------------
# Ontology header + import loading
# ---------------------------------------------------------------------------


def _get_ontology_iri(g: Graph) -> URIRef | None:
    for s in g.subjects(RDF.type, OWL.Ontology):
        if isinstance(s, URIRef):
            return s
    return None


def _get_import_iris(g: Graph) -> list[URIRef]:
    return [o for o in g.objects(None, OWL.imports) if isinstance(o, URIRef)]


# Cache: maps a search-root directory to a dict { ontology_iri: ttl_path }.
_LOCAL_ONTOLOGY_INDEX: dict[str, dict[str, str]] = {}

# Directories pruned during the local ontology walk to avoid pulling in
# unrelated TTLs (large monorepos can have hundreds of broken sample files).
_PRUNE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "site-packages",
}


def _build_local_ontology_index(search_root: str) -> dict[str, str]:
    """
    Walk *search_root* and index every .ttl file directly under an `ontologies/`
    subdirectory by the IRI of its declared `owl:Ontology` subject. Cached per root.
    """
    if search_root in _LOCAL_ONTOLOGY_INDEX:
        return _LOCAL_ONTOLOGY_INDEX[search_root]

    index: dict[str, str] = {}
    try:
        for dirpath, dirnames, filenames in os.walk(search_root):
            # Prune noisy directories in-place to skip them entirely.
            dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]

            # Only consider files inside an `ontologies` subtree, which is
            # where every ABI/Nexus/marketplace ontology lives.
            parts = set(os.path.normpath(dirpath).split(os.sep))
            if "ontologies" not in parts:
                continue

            for fname in filenames:
                if not fname.endswith(".ttl"):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    g = Graph()
                    # Suppress rdflib warnings on malformed sample TTLs.
                    import contextlib

                    with (
                        open(os.devnull, "w") as devnull,
                        contextlib.redirect_stderr(devnull),
                    ):
                        g.parse(fpath, format="turtle")
                    for s in g.subjects(RDF.type, OWL.Ontology):
                        if isinstance(s, URIRef):
                            index.setdefault(str(s), fpath)
                except Exception:
                    continue
    except Exception:
        pass

    _LOCAL_ONTOLOGY_INDEX[search_root] = index
    return index


def _find_project_root(base_dir: str) -> str:
    """
    Walk up from *base_dir* until we find a directory containing a project
    marker (pyproject.toml / .git / Makefile). Returns that dir, or *base_dir*
    if nothing is found.
    """
    current = os.path.abspath(base_dir)
    while True:
        if any(
            os.path.exists(os.path.join(current, marker))
            for marker in ("pyproject.toml", ".git", "Makefile")
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.abspath(base_dir)
        current = parent


def _resolve_local_import(iri_str: str, base_dir: str) -> str | None:
    """
    Look for a local .ttl file whose `<X> a owl:Ontology` triple matches *iri_str*.
    Indexes the entire project root (once, cached).
    """
    project_root = _find_project_root(base_dir)
    index = _build_local_ontology_index(project_root)
    return index.get(iri_str)


def _load_import(import_iri: URIRef, base_dir: str) -> tuple[Graph | None, str, str]:
    iri_str = str(import_iri)

    local_path: str | None = None
    if iri_str.startswith("file://"):
        local_path = iri_str[7:]
    elif "://" not in iri_str:
        local_path = (
            iri_str if os.path.isabs(iri_str) else os.path.join(base_dir, iri_str)
        )

    if local_path:
        if os.path.exists(local_path):
            ig = Graph()
            try:
                ig.parse(local_path, format="turtle")
                return ig, "ok", f"Loaded from local path: {local_path}"
            except Exception as exc:
                return None, "failed", f"Local file found but parse failed: {exc}"

    # Try to resolve the IRI against local ontology files (walk parent dirs).
    resolved = _resolve_local_import(iri_str, base_dir)
    if resolved:
        ig = Graph()
        try:
            ig.parse(resolved, format="turtle")
            return ig, "ok", f"Resolved IRI to local file: {resolved}"
        except Exception as exc:
            return None, "failed", f"Resolved to {resolved} but parse failed: {exc}"

    if iri_str.startswith("http://") or iri_str.startswith("https://"):
        try:
            req = urllib.request.Request(
                iri_str,
                headers={"Accept": "text/turtle, application/rdf+xml;q=0.9, */*;q=0.8"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310  # nosec B310
                raw = resp.read()
            ig = Graph()
            for fmt in ("turtle", "xml", "n3"):
                try:
                    ig.parse(data=raw, format=fmt)
                    return ig, "ok", f"Fetched via HTTP ({fmt}): {iri_str}"
                except Exception:
                    continue
            return (
                None,
                "failed",
                f"Fetched but could not parse in any known format: {iri_str}",
            )
        except urllib.error.URLError as exc:
            return None, "failed", f"HTTP fetch failed: {exc}"
        except Exception as exc:
            return None, "failed", f"Unexpected error fetching {iri_str}: {exc}"

    return None, "failed", f"Could not resolve import locally or via HTTP: {iri_str}"


# ---------------------------------------------------------------------------
# Individual checks — each returns a list of issue dicts
# ---------------------------------------------------------------------------


def check_ontology_header(g: Graph) -> list[dict]:
    """Verify the file declares exactly one owl:Ontology subject."""
    issues: list[dict] = []
    ontology_subjects = list(g.subjects(RDF.type, OWL.Ontology))

    if not ontology_subjects:
        issues.append(
            {
                "severity": "ERROR",
                "category": "ONTOLOGY_HEADER",
                "subject": "(file)",
                "message": (
                    "No owl:Ontology declaration found. "
                    "Every ontology file must contain exactly one "
                    "'<IRI> a owl:Ontology' triple."
                ),
            }
        )
    elif len(ontology_subjects) > 1:
        issues.append(
            {
                "severity": "WARNING",
                "category": "ONTOLOGY_HEADER",
                "subject": "(file)",
                "message": (
                    f"Multiple owl:Ontology subjects found "
                    f"({len(ontology_subjects)}): "
                    + ", ".join(str(s) for s in ontology_subjects)
                    + ". Expected exactly one."
                ),
            }
        )
    return issues


def load_imports(
    g: Graph,
    base_dir: str,
) -> tuple[Graph, list[dict]]:
    """
    Resolve owl:imports transitively, merging every loadable graph into a
    single combined graph. Each import is only loaded once.
    """
    records: list[dict] = []

    combined = Graph()
    for prefix, ns in g.namespaces():
        combined.bind(prefix, ns)
    for triple in g:
        combined.add(triple)

    visited: set[str] = set()
    queue: list[tuple[URIRef, str]] = [(iri, base_dir) for iri in _get_import_iris(g)]

    while queue:
        iri, current_dir = queue.pop(0)
        iri_str = str(iri)
        if iri_str in visited:
            continue
        visited.add(iri_str)

        ig, status, message = _load_import(iri, current_dir)
        records.append(
            {
                "iri": iri_str,
                "status": status,
                "message": message,
            }
        )
        if ig is None:
            continue

        for triple in ig:
            combined.add(triple)
        for prefix, ns in ig.namespaces():
            combined.bind(prefix, ns)

        # Recurse into nested imports. Use the parent dir of whatever local
        # file backed the import as the new search base for relative lookups.
        nested_dir = current_dir
        if message.startswith("Resolved IRI to local file:") or message.startswith(
            "Loaded from local path:"
        ):
            try:
                local_path = message.split(":", 1)[1].strip()
                nested_dir = os.path.dirname(os.path.abspath(local_path))
            except Exception:
                pass

        for nested in _get_import_iris(ig):
            if str(nested) not in visited:
                queue.append((nested, nested_dir))

    return combined, records


def check_parse(ttl_path: str) -> tuple[Graph | None, list[dict]]:
    g = Graph()
    try:
        g.parse(ttl_path, format="turtle")
        return g, []
    except Exception as exc:
        return None, [
            {
                "severity": "ERROR",
                "category": "PARSE",
                "subject": ttl_path,
                "message": f"File could not be parsed as Turtle: {exc}",
            }
        ]


def check_annotations(g: Graph) -> list[dict]:
    issues = []
    targets = [(c, "class") for c in _named_classes(g)] + [
        (p, "object property") for p in _named_object_properties(g)
    ]
    for iri, kind in targets:
        for ann_prop, ann_name in REQUIRED_ANNOTATIONS:
            if not g.value(iri, ann_prop):
                issues.append(
                    {
                        "severity": "WARNING",
                        "category": "ANNOTATION",
                        "subject": _short(iri, g),
                        "message": (
                            f"{kind.capitalize()} '{_label(iri, g)}' "
                            f"is missing {ann_name}."
                        ),
                    }
                )
    return issues


def check_bucket_mapping(
    g: Graph, main_classes: set[URIRef] | None = None
) -> list[dict]:
    issues = []
    bfo_prefix = str(BFO)

    targets = main_classes if main_classes is not None else set(_named_classes(g))

    for cls in targets:
        if str(cls).startswith(bfo_prefix):
            continue

        ancestors = _all_superclasses(cls, g)
        bucket_ancestors = ancestors & ALL_BUCKET_ROOTS

        if not bucket_ancestors:
            issues.append(
                {
                    "severity": "ERROR",
                    "category": "BUCKET_MAPPING",
                    "subject": _short(cls, g),
                    "message": (
                        f"Class '{_label(cls, g)}' does not subclass any BFO "
                        f"7 Buckets root. Every domain class must trace back "
                        f"to one of: "
                        + ", ".join(
                            f"{name} ({_short(iri, g)})"
                            for name, iri in BUCKET_ROOTS.items()
                        )
                        + "."
                    ),
                }
            )

    return issues


def check_property_domain_range(g: Graph) -> list[dict]:
    issues = []
    for prop in _named_object_properties(g):
        if not g.value(prop, RDFS.domain):
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "PROPERTY_DOMAIN",
                    "subject": _short(prop, g),
                    "message": (
                        f"Object property '{_label(prop, g)}' "
                        f"has no rdfs:domain declared."
                    ),
                }
            )
        if not g.value(prop, RDFS.range):
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "PROPERTY_RANGE",
                    "subject": _short(prop, g),
                    "message": (
                        f"Object property '{_label(prop, g)}' "
                        f"has no rdfs:range declared."
                    ),
                }
            )
    return issues


def check_orphan_properties(g: Graph) -> list[dict]:
    issues = []
    used_in_restrictions = _all_properties_used_in_restrictions(g)
    used_as_superproperty = {
        o for o in g.objects(None, RDFS.subPropertyOf) if isinstance(o, URIRef)
    }
    used_as_inverse = {
        o for o in g.objects(None, OWL.inverseOf) if isinstance(o, URIRef)
    }

    for prop in _named_object_properties(g):
        if (
            prop not in used_in_restrictions
            and prop not in used_as_superproperty
            and prop not in used_as_inverse
        ):
            used_as_predicate = any(True for _ in g.subject_objects(prop))
            if not used_as_predicate:
                issues.append(
                    {
                        "severity": "WARNING",
                        "category": "PROPERTY_ORPHAN",
                        "subject": _short(prop, g),
                        "message": (
                            f"Object property '{_label(prop, g)}' is declared "
                            f"but never used in any class restriction, "
                            f"subPropertyOf chain, inverseOf, or triple."
                        ),
                    }
                )
    return issues


_VOCAB_PREFIXES_FOR_RESTRICTIONS = (
    "http://purl.obolibrary.org/obo/",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2002/07/owl#",
    "http://www.w3.org/2004/02/skos/core#",
    "https://www.commoncoreontologies.org/",
)


def check_restriction_references(g: Graph) -> list[dict]:
    issues = []
    declared_classes = set(_named_classes(g))
    declared_properties = set(_named_object_properties(g))
    declared_data_properties = {
        s for s in g.subjects(RDF.type, OWL.DatatypeProperty) if isinstance(s, URIRef)
    }

    def _is_known(iri: URIRef) -> bool:
        s = str(iri)
        if any(s.startswith(p) for p in _VOCAB_PREFIXES_FOR_RESTRICTIONS):
            return True
        return (
            iri in declared_classes
            or iri in declared_properties
            or iri in declared_data_properties
            or (iri, RDF.type, None) in g
        )

    for bnode in g.subjects(RDF.type, OWL.Restriction):
        on_prop = g.value(bnode, OWL.onProperty)
        if isinstance(on_prop, URIRef) and not _is_known(on_prop):
            owner = g.value(None, RDFS.subClassOf, bnode)
            if owner is None:
                continue
            issues.append(
                {
                    "severity": "ERROR",
                    "category": "RESTRICTION_REF",
                    "subject": _short(owner, g) if owner else "unknown",
                    "message": (
                        f"Restriction on class '{_label(URIRef(str(owner)), g) if owner else '?'}' "
                        f"references undeclared property '{_short(on_prop, g)}'."
                    ),
                }
            )

        for filler_pred in (OWL.allValuesFrom, OWL.someValuesFrom):
            filler = g.value(bnode, filler_pred)
            if isinstance(filler, URIRef) and not _is_known(filler):
                owner = g.value(None, RDFS.subClassOf, bnode)
                if owner is None:
                    continue
                issues.append(
                    {
                        "severity": "ERROR",
                        "category": "RESTRICTION_REF",
                    "subject": _short(owner, g) if owner else "unknown",
                    "message": (
                        f"Restriction on class '{_label(URIRef(str(owner)), g) if owner else '?'}' "
                        f"references undeclared class '{_short(filler, g)}' "
                            f"in {_short(filler_pred, g)}."
                        ),
                    }
                )
    return issues


def _collect_all_restrictions(g: Graph, cls: URIRef) -> list[dict]:
    visited_classes: set[URIRef] = set()
    restrictions: list[dict] = []

    def _walk(c: URIRef) -> None:
        if c in visited_classes:
            return
        visited_classes.add(c)
        for parent in g.objects(c, RDFS.subClassOf):
            if isinstance(parent, BNode):
                if g.value(parent, RDF.type) == OWL.Restriction:
                    on_prop = g.value(parent, OWL.onProperty)
                    if not isinstance(on_prop, URIRef):
                        continue
                    avf = g.value(parent, OWL.allValuesFrom)
                    svf = g.value(parent, OWL.someValuesFrom)
                    if avf is not None:
                        quantifier, filler = (
                            "allValuesFrom",
                            avf if isinstance(avf, URIRef) else None,
                        )
                    elif svf is not None:
                        quantifier, filler = (
                            "someValuesFrom",
                            svf if isinstance(svf, URIRef) else None,
                        )
                    else:
                        quantifier, filler = "other", None
                    restrictions.append(
                        {
                            "cls": c,
                            "on_prop": on_prop,
                            "quantifier": quantifier,
                            "filler": filler,
                            "bnode": parent,
                        }
                    )
            elif isinstance(parent, URIRef):
                _walk(parent)

    _walk(cls)
    return restrictions


def check_restriction_inheritance(
    g: Graph, main_only_classes: set[URIRef]
) -> list[dict]:
    issues = []
    bfo_prefix = str(BFO)

    for cls in main_only_classes:
        if str(cls).startswith(bfo_prefix):
            continue

        all_restrictions = _collect_all_restrictions(g, cls)

        own_restrictions = [r for r in all_restrictions if r["cls"] == cls]
        own_by_prop: dict[URIRef, list[dict]] = defaultdict(list)
        for r in own_restrictions:
            own_by_prop[r["on_prop"]].append(r)

        ancestor_restrictions = [r for r in all_restrictions if r["cls"] != cls]
        ancestor_by_prop: dict[URIRef, list[dict]] = defaultdict(list)
        for r in ancestor_restrictions:
            ancestor_by_prop[r["on_prop"]].append(r)

        for prop, ancestor_rs in ancestor_by_prop.items():
            own_rs = own_by_prop.get(prop, [])

            ancestor_avf = [
                r
                for r in ancestor_rs
                if r["quantifier"] == "allValuesFrom" and r["filler"]
            ]
            own_avf = [
                r for r in own_rs if r["quantifier"] == "allValuesFrom" and r["filler"]
            ]

            for o_r in own_avf:
                for a_r in ancestor_avf:
                    if o_r["filler"] == a_r["filler"]:
                        continue
                    child_ancestors = _all_superclasses(o_r["filler"], g)
                    if a_r["filler"] not in child_ancestors:
                        issues.append(
                            {
                                "severity": "WARNING",
                                "category": "RESTRICTION_INHERIT",
                                "subject": _short(cls, g),
                                "message": (
                                    f"'{_label(cls, g)}' declares "
                                    f"allValuesFrom {_short(prop, g)} → "
                                    f"'{_short(o_r['filler'], g)}', "
                                    f"but ancestor '{_label(a_r['cls'], g)}' "
                                    f"restricts the same property to "
                                    f"'{_short(a_r['filler'], g)}'. "
                                    f"'{_short(o_r['filler'], g)}' is not declared "
                                    f"as a subclass of '{_short(a_r['filler'], g)}' "
                                    f"— this may silently contradict the parent constraint."
                                ),
                            }
                        )

            ancestor_svf = [
                r
                for r in ancestor_rs
                if r["quantifier"] == "someValuesFrom" and r["filler"]
            ]
            for a_r in ancestor_svf:
                for o_r in own_avf:
                    if o_r["filler"] is None or a_r["filler"] is None:
                        continue
                    if o_r["filler"] == a_r["filler"]:
                        continue
                    child_filler_ancestors = _all_superclasses(o_r["filler"], g)
                    anc_filler_ancestors = _all_superclasses(a_r["filler"], g)
                    if (
                        a_r["filler"] not in child_filler_ancestors
                        and o_r["filler"] not in anc_filler_ancestors
                    ):
                        issues.append(
                            {
                                "severity": "ERROR",
                                "category": "RESTRICTION_INHERIT",
                                "subject": _short(cls, g),
                                "message": (
                                    f"'{_label(cls, g)}' declares "
                                    f"allValuesFrom {_short(prop, g)} → "
                                    f"'{_short(o_r['filler'], g)}', "
                                    f"but ancestor '{_label(a_r['cls'], g)}' "
                                    f"requires someValuesFrom {_short(prop, g)} → "
                                    f"'{_short(a_r['filler'], g)}'. "
                                    f"The child's universal restriction may make "
                                    f"the ancestor's existential unsatisfiable."
                                ),
                            }
                        )

            for a_r in ancestor_svf:
                if not own_rs:
                    issues.append(
                        {
                            "severity": "INFO",
                            "category": "RESTRICTION_INHERIT",
                            "subject": _short(cls, g),
                            "message": (
                                f"'{_label(cls, g)}' inherits a someValuesFrom "
                                f"restriction on {_short(prop, g)} → "
                                f"'{_short(a_r['filler'], g)}' "
                                f"from ancestor '{_label(a_r['cls'], g)}' "
                                f"but declares no restriction of its own on "
                                f"this property. Consider re-declaring it "
                                f"explicitly if this class plays a distinct role."
                            ),
                        }
                    )
                    break

    return issues


def check_license(g: Graph) -> list[dict]:
    DC = Namespace("http://purl.org/dc/terms/")
    DC11 = Namespace("http://purl.org/dc/elements/1.1/")
    issues: list[dict] = []
    onto_iri = _get_ontology_iri(g)
    if onto_iri is None:
        return issues
    has_license = (
        g.value(onto_iri, DC["license"]) is not None
        or g.value(onto_iri, DC11["license"]) is not None
        or g.value(onto_iri, URIRef("http://purl.org/dc/terms/license")) is not None
    )
    if not has_license:
        issues.append(
            {
                "severity": "WARNING",
                "category": "LICENSE_MISSING",
                "subject": _short(onto_iri, g),
                "message": (
                    f"Ontology '{onto_iri}' does not declare a license "
                    f"(dc:license or dc11:license). A license is required "
                    f"for reuse clarity."
                ),
            }
        )
    return issues


def check_duplicate_labels(g: Graph, main_classes: set[URIRef]) -> list[dict]:
    issues = []
    label_map: dict[str, list[URIRef]] = defaultdict(list)
    for cls in main_classes:
        for lbl in g.objects(cls, RDFS.label):
            label_map[str(lbl).lower()].append(cls)
    for lbl_text, classes in label_map.items():
        if len(classes) > 1:
            subjects = ", ".join(_short(c, g) for c in classes)
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "DUPLICATE_LABEL",
                    "subject": subjects,
                    "message": (
                        f"Label '{lbl_text}' is shared by {len(classes)} classes: "
                        f"{subjects}. Each class should have a unique label."
                    ),
                }
            )
    return issues


def check_naming_convention(
    g: Graph, main_classes: set[URIRef], main_properties: set[URIRef]
) -> list[dict]:
    issues = []

    def _local(iri: URIRef) -> str:
        s = str(iri)
        return s.split("/")[-1].split("#")[-1]

    def _is_upper_camel(name: str) -> bool:
        return bool(re.match(r"^[A-Z][a-zA-Z0-9]*$", name))

    def _is_lower_camel(name: str) -> bool:
        return bool(re.match(r"^[a-z][a-zA-Z0-9]*$", name))

    def _has_delimiter(name: str) -> bool:
        return "_" in name or "-" in name

    for cls in main_classes:
        name = _local(cls)
        if not name:
            continue
        if _has_delimiter(name):
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "NAMING_CONVENTION",
                    "subject": _short(cls, g),
                    "message": (
                        f"Class '{name}' uses delimiter characters (_ or -). "
                        f"Classes should use UpperCamelCase (e.g. 'ServiceLine')."
                    ),
                }
            )
        elif not _is_upper_camel(name):
            issues.append(
                {
                    "severity": "INFO",
                    "category": "NAMING_CONVENTION",
                    "subject": _short(cls, g),
                    "message": (
                        f"Class '{name}' does not follow UpperCamelCase convention."
                    ),
                }
            )

    for prop in main_properties:
        name = _local(prop)
        if not name:
            continue
        if _has_delimiter(name):
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "NAMING_CONVENTION",
                    "subject": _short(prop, g),
                    "message": (
                        f"Property '{name}' uses delimiter characters (_ or -). "
                        f"Properties should use lowerCamelCase (e.g. 'hasExpertise')."
                    ),
                }
            )
        elif not _is_lower_camel(name):
            issues.append(
                {
                    "severity": "INFO",
                    "category": "NAMING_CONVENTION",
                    "subject": _short(prop, g),
                    "message": (
                        f"Property '{name}' does not follow lowerCamelCase convention."
                    ),
                }
            )
    return issues


def check_uri_file_extension(
    g: Graph, main_classes: set[URIRef], main_properties: set[URIRef]
) -> list[dict]:
    BAD_EXTENSIONS = (".owl", ".rdf", ".ttl", ".n3", ".rdfxml", ".xml")
    issues = []

    targets: list[tuple[URIRef, str]] = []
    onto_iri = _get_ontology_iri(g)
    if onto_iri:
        targets.append((onto_iri, "ontology IRI"))
    for cls in main_classes:
        targets.append((cls, "class"))
    for prop in main_properties:
        targets.append((prop, "property"))

    for iri, kind in targets:
        s = str(iri).lower().split("?")[0].split("#")[0]
        for ext in BAD_EXTENSIONS:
            if s.endswith(ext):
                issues.append(
                    {
                        "severity": "WARNING",
                        "category": "URI_FILE_EXTENSION",
                        "subject": _short(iri, g),
                        "message": (
                            f"The {kind} IRI '{iri}' ends with '{ext}'. "
                            f"IRIs should be stable identifiers, not file paths."
                        ),
                    }
                )
                break
    return issues


def check_is_property(g: Graph, main_properties: set[URIRef]) -> list[dict]:
    issues = []
    for prop in main_properties:
        local = str(prop).split("/")[-1].split("#")[-1].lower()
        label = str(g.value(prop, RDFS.label) or "").lower().strip()
        if local == "is" or label == "is":
            issues.append(
                {
                    "severity": "ERROR",
                    "category": "IS_PROPERTY",
                    "subject": _short(prop, g),
                    "message": (
                        f"Property '{_label(prop, g)}' appears to encode an 'is' "
                        f"relationship. Use rdfs:subClassOf for subclass relations, "
                        f"rdf:type for class membership, or owl:sameAs for equality."
                    ),
                }
            )
    return issues


def check_synonym_classes(g: Graph, main_classes: set[URIRef]) -> list[dict]:
    issues = []
    onto_iri = _get_ontology_iri(g)
    onto_ns = str(onto_iri).rsplit("/", 1)[0] + "/" if onto_iri else None

    for cls in main_classes:
        for equiv in g.objects(cls, OWL.equivalentClass):
            if not isinstance(equiv, URIRef):
                continue
            if equiv == cls:
                continue
            if (
                onto_ns
                and str(equiv).startswith(onto_ns)
                and str(cls).startswith(onto_ns)
            ):
                issues.append(
                    {
                        "severity": "WARNING",
                        "category": "SYNONYM_CLASS",
                        "subject": _short(cls, g),
                        "message": (
                            f"'{_label(cls, g)}' is declared equivalent to "
                            f"'{_label(equiv, g)}' within the same namespace. "
                            f"If these are synonyms, use skos:altLabel on one "
                            f"class rather than two equivalent classes."
                        ),
                    }
                )
    return issues


def check_unconnected_elements(
    g: Graph, main_classes: set[URIRef], main_properties: set[URIRef]
) -> list[dict]:
    issues = []
    bfo_prefix = str(BFO)

    referenced: set[URIRef] = set()
    for _, _, o in g:
        if isinstance(o, URIRef):
            referenced.add(o)

    for cls in main_classes:
        if str(cls).startswith(bfo_prefix):
            continue
        has_parent = any(True for _ in g.objects(cls, RDFS.subClassOf))
        has_child = any(True for _ in g.subjects(RDFS.subClassOf, cls))
        is_referred = cls in referenced
        if not has_parent and not has_child and not is_referred:
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "UNCONNECTED",
                    "subject": _short(cls, g),
                    "message": (
                        f"Class '{_label(cls, g)}' has no subClassOf, no subclasses, "
                        f"and is not referenced from any other element. "
                        f"It is isolated from the rest of the ontology."
                    ),
                }
            )

    used_in_restrictions_cache = _all_properties_used_in_restrictions(g)
    for prop in main_properties:
        if str(prop).startswith(bfo_prefix):
            continue
        has_domain = g.value(prop, RDFS.domain) is not None
        has_range = g.value(prop, RDFS.range) is not None
        used_in_res = prop in used_in_restrictions_cache
        is_referred = prop in referenced
        if not has_domain and not has_range and not used_in_res and not is_referred:
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "UNCONNECTED",
                    "subject": _short(prop, g),
                    "message": (
                        f"Property '{_label(prop, g)}' has no domain, no range, "
                        f"is not used in any restriction, and is not referenced "
                        f"from any other element."
                    ),
                }
            )
    return issues


def check_untyped_use(g: Graph) -> list[dict]:
    issues = []
    KNOWN_PREFIXES = (
        "http://purl.obolibrary.org/obo/",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "http://www.w3.org/2000/01/rdf-schema#",
        "http://www.w3.org/2002/07/owl#",
        "http://www.w3.org/2004/02/skos/core#",
        "http://purl.org/dc/",
        "https://www.commoncoreontologies.org/",
    )

    declared_classes = {
        s for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)
    }
    declared_classes |= {
        s for s in g.subjects(RDF.type, RDFS.Class) if isinstance(s, URIRef)
    }
    declared_properties = {
        s for s in g.subjects(RDF.type, OWL.ObjectProperty) if isinstance(s, URIRef)
    }
    declared_properties |= {
        s for s in g.subjects(RDF.type, OWL.DatatypeProperty) if isinstance(s, URIRef)
    }
    declared_properties |= {
        s for s in g.subjects(RDF.type, RDF.Property) if isinstance(s, URIRef)
    }

    def _is_vocab(iri: URIRef) -> bool:
        return any(str(iri).startswith(p) for p in KNOWN_PREFIXES)

    class_uses: set[URIRef] = set()
    for o in g.objects(None, RDFS.subClassOf):
        if isinstance(o, URIRef):
            class_uses.add(o)
    for o in g.objects(None, RDF.type):
        if isinstance(o, URIRef):
            class_uses.add(o)
    for pred in (
        OWL.allValuesFrom,
        OWL.someValuesFrom,
        OWL.unionOf,
        OWL.intersectionOf,
    ):
        for o in g.objects(None, pred):
            if isinstance(o, URIRef):
                class_uses.add(o)

    for iri in class_uses:
        if _is_vocab(iri):
            continue
        if iri not in declared_classes and iri not in declared_properties:
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "UNTYPED_USE",
                    "subject": _short(iri, g),
                    "message": (
                        f"'{iri}' is used in a class position (subClassOf, rdf:type, "
                        f"or restriction filler) but is never declared as owl:Class."
                    ),
                }
            )

    prop_uses: set[URIRef] = set()
    for o in g.objects(None, OWL.onProperty):
        if isinstance(o, URIRef):
            prop_uses.add(o)
    for pred in (RDFS.domain, RDFS.range):
        for s in g.subjects(pred, None):
            if isinstance(s, URIRef):
                prop_uses.add(s)

    for iri in prop_uses:
        if _is_vocab(iri):
            continue
        if iri not in declared_properties and iri not in declared_classes:
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "UNTYPED_USE",
                    "subject": _short(iri, g),
                    "message": (
                        f"'{iri}' is used in a property position (onProperty, "
                        f"domain, or range) but is never declared as owl:ObjectProperty "
                        f"or owl:DatatypeProperty."
                    ),
                }
            )
    return issues


def check_multi_domain_range(g: Graph, main_properties: set[URIRef]) -> list[dict]:
    issues = []
    for prop in main_properties:
        domains = list(g.objects(prop, RDFS.domain))
        ranges = list(g.objects(prop, RDFS.range))
        if len(domains) > 1:
            issues.append(
                {
                    "severity": "ERROR",
                    "category": "MULTI_DOMAIN_RANGE",
                    "subject": _short(prop, g),
                    "message": (
                        f"Property '{_label(prop, g)}' has {len(domains)} rdfs:domain "
                        f"statements ({', '.join(_short(d, g) for d in domains)}). "
                        f"Multiple domains are interpreted as intersection (AND), "
                        f"not union. Use owl:unionOf in a single domain if OR is intended."
                    ),
                }
            )
        if len(ranges) > 1:
            issues.append(
                {
                    "severity": "ERROR",
                    "category": "MULTI_DOMAIN_RANGE",
                    "subject": _short(prop, g),
                    "message": (
                        f"Property '{_label(prop, g)}' has {len(ranges)} rdfs:range "
                        f"statements ({', '.join(_short(r, g) for r in ranges)}). "
                        f"Multiple ranges are interpreted as intersection (AND), "
                        f"not union. Use owl:unionOf in a single range if OR is intended."
                    ),
                }
            )
    return issues


def check_missing_disjointness(g: Graph, main_classes: set[URIRef]) -> list[dict]:
    issues = []
    bfo_prefix = str(BFO)

    parent_children: dict[URIRef, set[URIRef]] = defaultdict(set)
    for cls in main_classes:
        if str(cls).startswith(bfo_prefix):
            continue
        for parent in g.objects(cls, RDFS.subClassOf):
            if isinstance(parent, URIRef):
                parent_children[parent].add(cls)

    disjoint_pairs: set[frozenset] = set()
    for s, _, o in g.triples((None, OWL.disjointWith, None)):
        if isinstance(s, URIRef) and isinstance(o, URIRef):
            disjoint_pairs.add(frozenset([s, o]))
    for bnode in g.subjects(RDF.type, OWL.AllDisjointClasses):
        members_node = g.value(bnode, OWL.members)
        if members_node:
            members = list(g.items(members_node))
            for i, a in enumerate(members):
                for b in members[i + 1 :]:
                    if isinstance(a, URIRef) and isinstance(b, URIRef):
                        disjoint_pairs.add(frozenset([a, b]))

    reported: set[frozenset] = set()
    for parent, children in parent_children.items():
        child_list = sorted(children, key=str)
        for i, a in enumerate(child_list):
            for b in child_list[i + 1 :]:
                pair = frozenset([a, b])
                if pair in disjoint_pairs or pair in reported:
                    continue
                reported.add(pair)
                issues.append(
                    {
                        "severity": "INFO",
                        "category": "MISSING_DISJOINT",
                        "subject": f"{_short(a, g)}, {_short(b, g)}",
                        "message": (
                            f"Sibling classes '{_label(a, g)}' and '{_label(b, g)}' "
                            f"share parent '{_label(parent, g)}' but have no "
                            f"owl:disjointWith between them. If they cannot share "
                            f"instances, add disjointness to improve reasoning."
                        ),
                    }
                )
    return issues


def check_recursive_definitions(
    g: Graph, main_classes: set[URIRef], main_properties: set[URIRef]
) -> list[dict]:
    issues = []

    for cls in main_classes:
        for parent in g.objects(cls, RDFS.subClassOf):
            if parent == cls:
                issues.append(
                    {
                        "severity": "ERROR",
                        "category": "RECURSIVE_DEF",
                        "subject": _short(cls, g),
                        "message": (
                            f"Class '{_label(cls, g)}' is listed as a subclass of itself "
                            f"via rdfs:subClassOf — this is a recursive definition."
                        ),
                    }
                )
        for equiv in g.objects(cls, OWL.equivalentClass):
            if equiv == cls:
                issues.append(
                    {
                        "severity": "ERROR",
                        "category": "RECURSIVE_DEF",
                        "subject": _short(cls, g),
                        "message": (
                            f"Class '{_label(cls, g)}' is declared equivalent to itself "
                            f"via owl:equivalentClass."
                        ),
                    }
                )

    for prop in main_properties:
        for pred in (RDFS.domain, RDFS.range):
            val = g.value(prop, pred)
            if val == prop:
                pred_label = "rdfs:domain" if pred == RDFS.domain else "rdfs:range"
                issues.append(
                    {
                        "severity": "ERROR",
                        "category": "RECURSIVE_DEF",
                        "subject": _short(prop, g),
                        "message": (
                            f"Property '{_label(prop, g)}' appears in its own "
                            f"{pred_label} — this is a recursive definition."
                        ),
                    }
                )
        for chain_node in g.objects(prop, OWL.propertyChainAxiom):
            for member in g.items(chain_node):
                if member == prop:
                    issues.append(
                        {
                            "severity": "ERROR",
                            "category": "RECURSIVE_DEF",
                            "subject": _short(prop, g),
                            "message": (
                                f"Property '{_label(prop, g)}' appears in its own "
                                f"owl:propertyChainAxiom."
                            ),
                        }
                    )
    return issues


def check_wrong_inverse(g: Graph, main_properties: set[URIRef]) -> list[dict]:
    issues = []
    checked: set[frozenset] = set()

    for prop in main_properties:
        inv = g.value(prop, OWL.inverseOf)
        if not isinstance(inv, URIRef):
            continue
        pair = frozenset([prop, inv])
        if pair in checked:
            continue
        checked.add(pair)

        dom_p = g.value(prop, RDFS.domain)
        rng_p = g.value(prop, RDFS.range)
        dom_i = g.value(inv, RDFS.domain)
        rng_i = g.value(inv, RDFS.range)

        if not all(isinstance(x, URIRef) for x in [dom_p, rng_p, dom_i, rng_i]):
            continue

        if dom_p != rng_i or rng_p != dom_i:
            issues.append(
                {
                    "severity": "ERROR",
                    "category": "WRONG_INVERSE",
                    "subject": _short(prop, g),
                    "message": (
                        f"'{_label(prop, g)}' ({_short(dom_p, g)} → {_short(rng_p, g)}) "
                        f"is declared inverse of '{_label(inv, g)}' "
                        f"({_short(dom_i, g)} → {_short(rng_i, g)}), "
                        f"but a true inverse requires domain(P)=range(Q) and "
                        f"range(P)=domain(Q). "
                        f"Expected: '{_label(inv, g)}' to be "
                        f"({_short(rng_p, g)} → {_short(dom_p, g)})."
                    ),
                }
            )
    return issues


def check_inverse_of_itself(g: Graph, main_properties: set[URIRef]) -> list[dict]:
    issues = []
    for prop in main_properties:
        inv = g.value(prop, OWL.inverseOf)
        if inv == prop:
            issues.append(
                {
                    "severity": "ERROR",
                    "category": "INVERSE_OF_ITSELF",
                    "subject": _short(prop, g),
                    "message": (
                        f"Property '{_label(prop, g)}' is declared as owl:inverseOf "
                        f"itself. A self-inverse property should be declared as "
                        f"owl:SymmetricProperty instead."
                    ),
                }
            )
    return issues


def check_inverse_of_symmetric(g: Graph, main_properties: set[URIRef]) -> list[dict]:
    issues = []
    symmetric_props = {
        s for s in g.subjects(RDF.type, OWL.SymmetricProperty) if isinstance(s, URIRef)
    }
    for prop in main_properties:
        if prop not in symmetric_props:
            continue
        inv = g.value(prop, OWL.inverseOf)
        if isinstance(inv, URIRef):
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "INVERSE_OF_SYMMETRIC",
                    "subject": _short(prop, g),
                    "message": (
                        f"Property '{_label(prop, g)}' is owl:SymmetricProperty "
                        f"and also declares owl:inverseOf '{_label(inv, g)}'. "
                        f"A symmetric property is its own inverse; "
                        f"the owl:inverseOf declaration is redundant."
                    ),
                }
            )
    return issues


def check_wrong_transitive(g: Graph, main_properties: set[URIRef]) -> list[dict]:
    issues = []
    transitive_props = {
        s for s in g.subjects(RDF.type, OWL.TransitiveProperty) if isinstance(s, URIRef)
    }
    for prop in main_properties:
        if prop not in transitive_props:
            continue
        dom = g.value(prop, RDFS.domain)
        rng = g.value(prop, RDFS.range)
        if not (isinstance(dom, URIRef) and isinstance(rng, URIRef)):
            continue
        if dom == rng:
            continue
        rng_ancestors = _all_superclasses(rng, g)
        if dom not in rng_ancestors:
            issues.append(
                {
                    "severity": "WARNING",
                    "category": "WRONG_TRANSITIVE",
                    "subject": _short(prop, g),
                    "message": (
                        f"Property '{_label(prop, g)}' is owl:TransitiveProperty "
                        f"but has domain '{_short(dom, g)}' and range '{_short(rng, g)}'. "
                        f"For transitivity to be sound, the range must be the same "
                        f"class as (or a subclass of) the domain so that chained "
                        f"applications stay type-consistent."
                    ),
                }
            )
    return issues


def check_circular_subclass(g: Graph) -> list[dict]:
    issues = []
    classes = _named_classes(g)

    direct_parents: dict[URIRef, set[URIRef]] = defaultdict(set)
    for cls in classes:
        for parent in g.objects(cls, RDFS.subClassOf):
            if isinstance(parent, URIRef):
                direct_parents[cls].add(parent)

    for cls in classes:
        for parent in direct_parents[cls]:
            for bnode in g.objects(parent, RDFS.subClassOf):
                if isinstance(bnode, BNode):
                    if g.value(bnode, RDF.type) == OWL.Restriction:
                        filler = g.value(bnode, OWL.someValuesFrom)
                        if filler == cls:
                            issues.append(
                                {
                                    "severity": "ERROR",
                                    "category": "CIRCULAR_SUBCLASS",
                                    "subject": _short(cls, g),
                                    "message": (
                                        f"'{_label(cls, g)}' is a subclass of "
                                        f"'{_label(parent, g)}', which in turn has "
                                        f"owl:someValuesFrom '{_label(cls, g)}'. "
                                        f"This creates a circular existential dependency."
                                    ),
                                }
                            )
    return issues


def check_inheres_in(g: Graph, main_classes: set[URIRef] | None = None) -> list[dict]:
    issues = []
    bfo_prefix = str(BFO)

    targets = main_classes if main_classes is not None else set(_named_classes(g))

    for cls in targets:
        if str(cls).startswith(bfo_prefix):
            continue

        ancestors = _all_superclasses(cls, g)
        bucket_hit = ancestors & REQUIRES_INHERES_IN
        if not bucket_hit:
            continue

        props_used = _restriction_properties(g, cls)

        if BFO_INHERES_IN not in props_used and BFO_BEARER_OF not in props_used:
            # Also check the property is reachable via subPropertyOf to inheres-in / bearer-of
            ok = False
            for p in props_used:
                supers = set()
                stack = [p]
                while stack:
                    cur = stack.pop()
                    if cur in supers:
                        continue
                    supers.add(cur)
                    for parent in g.objects(cur, RDFS.subPropertyOf):
                        if isinstance(parent, URIRef):
                            stack.append(parent)
                if BFO_INHERES_IN in supers or BFO_BEARER_OF in supers:
                    ok = True
                    break

            if ok:
                continue

            bucket_name = next(
                name for name, iri in BUCKET_ROOTS.items() if iri in bucket_hit
            )
            issues.append(
                {
                    "severity": "ERROR",
                    "category": "INHERES_IN",
                    "subject": _short(cls, g),
                    "message": (
                        f"Class '{_label(cls, g)}' subclasses {bucket_name} "
                        f"but has no owl:Restriction using bfo:BFO_0000197 "
                        f"(inheres in) or bfo:BFO_0000196 (bearer of) "
                        f"(directly or via subPropertyOf). "
                        f"Qualities, roles, and dispositions must be anchored "
                        f"to a bearer."
                    ),
                }
            )
    return issues


def check_inverse_missing(g: Graph) -> list[dict]:
    issues = []
    props = _named_object_properties(g)

    dr_map: dict[tuple, URIRef] = {}
    for prop in props:
        dom = g.value(prop, RDFS.domain)
        rng = g.value(prop, RDFS.range)
        if isinstance(dom, URIRef) and isinstance(rng, URIRef):
            dr_map[(dom, rng)] = prop

    declared_inverses: set[frozenset] = set()
    for prop in props:
        inv = g.value(prop, OWL.inverseOf)
        if inv:
            declared_inverses.add(frozenset([prop, inv]))

    for prop in props:
        dom = g.value(prop, RDFS.domain)
        rng = g.value(prop, RDFS.range)
        if not (isinstance(dom, URIRef) and isinstance(rng, URIRef)):
            continue
        candidate_inverse = dr_map.get((rng, dom))
        if candidate_inverse and candidate_inverse != prop:
            pair = frozenset([prop, candidate_inverse])
            if pair not in declared_inverses:
                issues.append(
                    {
                        "severity": "INFO",
                        "category": "INVERSE_MISSING",
                        "subject": _short(prop, g),
                        "message": (
                            f"'{_label(prop, g)}' ({_short(dom, g)} → {_short(rng, g)}) "
                            f"and '{_label(candidate_inverse, g)}' "
                            f"({_short(rng, g)} → {_short(dom, g)}) appear to be "
                            f"inverses but neither declares owl:inverseOf the other."
                        ),
                    }
                )
    return issues


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------


def validate(ttl_path: str, raise_error: bool = False) -> dict:
    """
    Run all checks against *ttl_path*.

    Parameters
    ----------
    ttl_path    : path to the Turtle file
    raise_error : if True, raise ValueError on the first ERROR-severity issue

    Returns
    -------
    A report dict with keys: summary, errors, warnings, info, imports
    """
    all_issues: list[dict] = []
    import_records: list[dict] = []
    base_dir = os.path.dirname(os.path.abspath(ttl_path))

    g_main, parse_issues = check_parse(ttl_path)
    all_issues.extend(parse_issues)
    if g_main is None:
        if raise_error:
            raise ValueError(parse_issues[0]["message"])
        return _build_report(all_issues, import_records)

    header_issues = check_ontology_header(g_main)
    all_issues.extend(header_issues)
    for issue in header_issues:
        if raise_error and issue["severity"] == "ERROR":
            raise ValueError(
                f"[{issue['category']}] {issue['subject']}: {issue['message']}"
            )

    g_combined, import_records = load_imports(g_main, base_dir)

    for rec in import_records:
        if rec["status"] == "failed":
            issue = {
                "severity": "WARNING",
                "category": "IMPORT_LOAD",
                "subject": rec["iri"],
                "message": rec["message"],
            }
            all_issues.append(issue)

    main_classes = set(
        s for s in g_main.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)
    )
    main_properties = set(
        s
        for s in g_main.subjects(RDF.type, OWL.ObjectProperty)
        if isinstance(s, URIRef)
    )

    def _run(fn, *args):
        issues = fn(*args)
        for issue in issues:
            all_issues.append(issue)
            if raise_error and issue["severity"] == "ERROR":
                raise ValueError(
                    f"[{issue['category']}] {issue['subject']}: {issue['message']}"
                )

    _run(check_annotations, g_combined)
    _run(check_license, g_combined)
    _run(check_duplicate_labels, g_combined, main_classes)
    _run(check_naming_convention, g_combined, main_classes, main_properties)
    _run(check_uri_file_extension, g_combined, main_classes, main_properties)
    _run(check_is_property, g_combined, main_properties)
    _run(check_synonym_classes, g_combined, main_classes)
    _run(check_unconnected_elements, g_combined, main_classes, main_properties)
    _run(check_untyped_use, g_combined)
    _run(check_multi_domain_range, g_combined, main_properties)
    _run(check_bucket_mapping, g_combined, main_classes)
    _run(check_property_domain_range, g_combined)
    _run(check_missing_disjointness, g_combined, main_classes)
    _run(check_orphan_properties, g_combined)
    _run(check_restriction_references, g_combined)
    _run(check_restriction_inheritance, g_combined, main_classes)
    _run(check_recursive_definitions, g_combined, main_classes, main_properties)
    _run(check_circular_subclass, g_combined)
    _run(check_inheres_in, g_combined, main_classes)
    _run(check_wrong_inverse, g_combined, main_properties)
    _run(check_inverse_of_itself, g_combined, main_properties)
    _run(check_inverse_of_symmetric, g_combined, main_properties)
    _run(check_wrong_transitive, g_combined, main_properties)
    _run(check_inverse_missing, g_combined)

    return _build_report(all_issues, import_records)


def _build_report(issues: list[dict], import_records: list[dict] | None = None) -> dict:
    errors = [i for i in issues if i["severity"] == "ERROR"]
    warnings = [i for i in issues if i["severity"] == "WARNING"]
    info = [i for i in issues if i["severity"] == "INFO"]

    by_category: dict[str, int] = defaultdict(int)
    for issue in issues:
        by_category[issue["category"]] += 1

    return {
        "summary": {
            "total": len(issues),
            "errors": len(errors),
            "warnings": len(warnings),
            "info": len(info),
            "by_category": dict(by_category),
        },
        "imports": import_records or [],
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a Turtle ontology against the BFO 7 Buckets framework."
    )
    parser.add_argument(
        "ttl_path",
        help="Path to the Turtle (.ttl) file to validate.",
    )
    parser.add_argument(
        "--raise-error",
        action="store_true",
        default=False,
        help=(
            "Stop on the first ERROR-severity issue and raise a ValueError. "
            "Default: collect all issues and print a full JSON report."
        ),
    )
    args = parser.parse_args()

    try:
        report = validate(args.ttl_path, raise_error=args.raise_error)
    except ValueError as exc:
        print(f"\nValidation stopped on first error:\n  {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if report["summary"]["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

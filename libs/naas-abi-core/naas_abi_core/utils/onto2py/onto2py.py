import hashlib
import importlib.util
import io
import os
import pkgutil
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import rdflib
from rdflib import BNode
from rdflib.collection import Collection

# Ontology checker lives in the parent utils/ directory next to this package.
_UTILS_DIR = str(Path(__file__).resolve().parent.parent)
if _UTILS_DIR not in sys.path:
    sys.path.insert(0, _UTILS_DIR)


def _run_ontology_check(ttl_file_path: str) -> None:
    """
    Run the static ontology checker on *ttl_file_path* before code generation.

    Raises ValueError listing every ERROR-severity issue found.
    Skipped silently if either of these is true:
      - ABI_SKIP_ONTOLOGY_CHECK=1 is set (emergency bypass)
      - The checker module cannot be imported (missing dep)
    """
    if os.environ.get("ABI_SKIP_ONTOLOGY_CHECK") == "1":
        return

    try:
        import ontology_checker  # type: ignore[import-not-found]
    except ImportError:
        return

    try:
        report = ontology_checker.check(
            source_path=ttl_file_path,
            layers=["static"],
            raise_error=False,
            no_raw=True,
        )
    except FileNotFoundError:
        raise
    except Exception as exc:
        # Never let a checker bug block onto2py — log and continue.
        print(
            f"⚠️  ontology_checker raised during validation of {ttl_file_path}: {exc}",
            file=sys.stderr,
        )
        return

    static = report.get("static", {}) or {}
    if static.get("skipped"):
        return

    errors: List[Dict[str, Any]] = static.get("errors", []) or []
    if not errors:
        return

    lines = [f"Ontology validation failed for {ttl_file_path}:"]
    for issue in errors:
        lines.append(
            f"  [{issue.get('category', 'ERROR')}] "
            f"{issue.get('subject', '?')}: {issue.get('message', '')}"
        )
    raise ValueError("\n".join(lines))


_CACHE_MARKER_PREFIX = "# onto2py-source-sha256: "
# Bump this when the generator output format changes so previously cached
# .py files are invalidated even when the source TTL hash matches.
_CACHE_KEY_VERSION = "3-annotation-locator"

# Annotation properties that let an ontology declare *where* it lives in the
# Python package tree, so cross-package `owl:imports <https://canonical-iri>`
# can resolve without leaking non-standard URI schemes into the TTL.
_ABI_PYTHON_PACKAGE = rdflib.URIRef("http://ontology.naas.ai/abi/pythonPackage")
_ABI_ONTOLOGY_RESOURCE = rdflib.URIRef("http://ontology.naas.ai/abi/ontologyResource")
_ABI_PYTHON_RESOURCE = rdflib.URIRef("http://ontology.naas.ai/abi/pythonResource")


@dataclass
class OntologyLocator:
    """How to load an indexed ontology.

    Either ``ttl_path`` (filesystem) is set, or the importlib triple
    (``python_package`` + ``ontology_resource``) is set, or both. When both
    are present the importlib path wins so we keep working inside wheels.
    """
    ttl_path: Optional[Path] = None
    python_package: Optional[str] = None
    ontology_resource: Optional[str] = None
    python_resource: Optional[str] = None


# Module-level caches for owl:imports resolution. Reused across calls so a
# multi-file generation pass doesn't re-walk the ontology tree for every TTL.
_IMPORT_FILE_CACHE: Dict[Tuple[str, str], Optional[OntologyLocator]] = {}
_IMPORT_GRAPH_CACHE: Dict[str, Optional[rdflib.Graph]] = {}
# Index of every ontology IRI declared under a given search root, mapped to
# its locator. Built lazily on first lookup so we only walk each ontologies
# tree once per process.
_ONTOLOGY_INDEX_CACHE: Dict[str, Dict[str, OntologyLocator]] = {}
# Cross-package index built by scanning every installed `naas_abi*` package.
# Lets an ontology in one package resolve `owl:imports` of an ontology that
# lives in a sibling package, without filesystem-relative paths.
_GLOBAL_ONTOLOGY_INDEX: Optional[Dict[str, OntologyLocator]] = None


@dataclass
class PropertyInfo:
    """Information about a property (data or object property)"""

    name: str
    property_type: str  # 'data' or 'object'
    range_classes: Dict[str, Optional[int]] = field(
        default_factory=dict
    )  # Dict mapping class name to cardinality (None = not specified, > 1 = list, 1 or 0 = single)
    datatype: Optional[str] = None
    required: bool = False
    description: Optional[str] = None  # skos:definition
    default_value: Optional[str] = (
        None  # Default value expression (e.g., "datetime.now()")
    )


@dataclass
class ClassInfo:
    """Information about an RDF class"""

    name: str
    uri: str
    parent_classes: List[str]
    properties: List[PropertyInfo]
    description: Optional[str] = None
    property_uris: Dict[str, str] = field(
        default_factory=dict
    )  # Maps property name to URI
    label: Optional[str] = None  # rdfs:label
    # If set, this class is sourced from another already-generated module
    # (resolved via owl:imports in the TTL). The generator must emit an
    # `import` for it instead of a class body, and must use this name as
    # the parent when subclasses reference its URI.
    external_module: Optional[str] = None


def extract_class_name_from_label(label: str) -> Optional[str]:
    """Extract a PascalCase class name from an rdfs:label"""
    if not label:
        return None

    # Remove spaces and convert to PascalCase
    # Split by spaces, then for each word: capitalize first letter, keep rest as-is
    words = label.strip().split()
    pascal_words = []
    for word in words:
        if word:
            # Capitalize first letter, preserve rest of the word's case
            pascal_word = word[0].upper() + word[1:] if len(word) > 0 else word
            pascal_words.append(pascal_word)

    pascal_name = "".join(pascal_words)

    # Clean up: remove any non-alphanumeric characters except underscores
    pascal_name = re.sub(r"[^a-zA-Z0-9_]", "", pascal_name)

    # Ensure it starts with a letter
    if not pascal_name or not pascal_name[0].isalpha():
        return None

    return pascal_name if pascal_name.isidentifier() else None


def extract_class_name(uri, g: Optional[rdflib.Graph] = None) -> Optional[str]:
    """Extract a clean class name from a URI, preferring rdfs:label if available"""
    # First try to get rdfs:label if graph is provided
    if g is not None:
        RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
        for label in g.objects(uri, RDFS.label):
            label_str = str(label)
            # Remove language tag if present (e.g., "Person"@en -> "Person")
            if "@" in label_str:
                label_str = label_str.split("@")[0]
            class_name = extract_class_name_from_label(label_str)
            if class_name:
                return class_name

    # Fall back to URI fragment if no label found
    uri_str = str(uri)
    if "#" in uri_str:
        name = uri_str.split("#")[-1]
    elif "/" in uri_str:
        name = uri_str.split("/")[-1]
    else:
        name = uri_str

    # Clean up the name to be a valid Python class name
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    if name and name[0].islower():
        name = name[0].upper() + name[1:]

    return name if name and name.isidentifier() else None


def extract_property_name_from_label(label: str) -> Optional[str]:
    """Extract a snake_case property name from an rdfs:label"""
    if not label:
        return None

    # Convert to lowercase and replace spaces with underscores
    name = label.strip().lower()
    name = re.sub(r"\s+", "_", name)  # Replace spaces with underscores

    # Clean up: remove any non-alphanumeric characters except underscores
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)

    # Remove leading/trailing underscores
    name = name.strip("_")

    # Ensure it's a valid identifier
    if not name or not name[0].isalpha():
        return None

    return name if name.isidentifier() else None


def extract_property_name(uri, g: Optional[rdflib.Graph] = None) -> Optional[str]:
    """Extract a clean property name from a URI, preferring rdfs:label if available"""
    # First try to get rdfs:label if graph is provided
    if g is not None:
        RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
        for label in g.objects(uri, RDFS.label):
            label_str = str(label)
            # Remove language tag if present (e.g., "concretizes"@en -> "concretizes")
            if "@" in label_str:
                label_str = label_str.split("@")[0]
            prop_name = extract_property_name_from_label(label_str)
            if prop_name:
                return prop_name

    # Fall back to URI fragment if no label found
    uri_str = str(uri)
    if "#" in uri_str:
        name = uri_str.split("#")[-1]
    elif "/" in uri_str:
        name = uri_str.split("/")[-1]
    else:
        name = uri_str

    # Clean up the name to be a valid Python property name
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    if name and name[0].isupper():
        name = name[0].lower() + name[1:]

    return name if name and name.isidentifier() else None


def extract_classes_from_union(
    g: rdflib.Graph, union_node: BNode, classes: Dict[str, ClassInfo]
) -> List[str]:
    """Extract class names from an owl:unionOf construct"""
    class_names = []
    try:
        # Use rdflib Collection to handle RDF lists
        collection = Collection(g, union_node)
        for item in collection:
            if isinstance(item, rdflib.URIRef):
                if str(item) in classes:
                    class_names.append(classes[str(item)].name)
                else:
                    class_name = extract_class_name(item, g)
                    if class_name:
                        class_names.append(class_name)
    except Exception:
        # Fallback: manual list traversal
        current = union_node
        while current and current != rdflib.RDF.nil:
            first = list(g.objects(current, rdflib.RDF.first))
            rest = list(g.objects(current, rdflib.RDF.rest))

            if first:
                first_item = first[0]
                if isinstance(first_item, rdflib.URIRef):
                    if str(first_item) in classes:
                        class_names.append(classes[str(first_item)].name)
                    else:
                        class_name = extract_class_name(first_item, g)
                        if class_name:
                            class_names.append(class_name)

            if rest and rest[0] != rdflib.RDF.nil and isinstance(rest[0], BNode):
                current = rest[0]
            else:
                break
    return class_names


def extract_classes_from_intersection(
    g: rdflib.Graph,
    intersection_node: BNode,
    classes: Dict[str, ClassInfo],
    OWL: rdflib.Namespace,
) -> List[str]:
    """Extract class names from an owl:intersectionOf construct"""
    class_names = []
    try:
        # Use rdflib Collection to handle RDF lists
        collection = Collection(g, intersection_node)
        for item in collection:
            if isinstance(item, rdflib.URIRef):
                # Direct class reference
                if str(item) in classes:
                    class_names.append(classes[str(item)].name)
                else:
                    class_name = extract_class_name(item, g)
                    if class_name:
                        class_names.append(class_name)
            elif isinstance(item, BNode):
                # Check if it's a nested restriction with owl:onClass
                on_class = list(g.objects(item, OWL.onClass))
                if on_class:
                    for cls in on_class:
                        if isinstance(cls, rdflib.URIRef):
                            if str(cls) in classes:
                                class_names.append(classes[str(cls)].name)
                            else:
                                class_name = extract_class_name(cls, g)
                                if class_name:
                                    class_names.append(class_name)
                # Check for allValuesFrom in nested restriction
                all_values = list(g.objects(item, OWL.allValuesFrom))
                for val in all_values:
                    if isinstance(val, rdflib.URIRef):
                        if str(val) in classes:
                            class_names.append(classes[str(val)].name)
                        else:
                            class_name = extract_class_name(val, g)
                            if class_name:
                                class_names.append(class_name)
    except Exception:
        # Fallback: manual list traversal
        current = intersection_node
        while current and current != rdflib.RDF.nil:
            first = list(g.objects(current, rdflib.RDF.first))
            rest = list(g.objects(current, rdflib.RDF.rest))

            if first:
                first_item = first[0]
                if isinstance(first_item, rdflib.URIRef):
                    if str(first_item) in classes:
                        class_names.append(classes[str(first_item)].name)
                    else:
                        class_name = extract_class_name(first_item, g)
                        if class_name:
                            class_names.append(class_name)
                elif isinstance(first_item, BNode):
                    # Check for owl:onClass in nested restriction
                    on_class = list(g.objects(first_item, OWL.onClass))
                    if on_class:
                        for cls in on_class:
                            if isinstance(cls, rdflib.URIRef):
                                if str(cls) in classes:
                                    class_names.append(classes[str(cls)].name)
                                else:
                                    class_name = extract_class_name(cls, g)
                                    if class_name:
                                        class_names.append(class_name)

            if rest and rest[0] != rdflib.RDF.nil and isinstance(rest[0], BNode):
                current = rest[0]
            else:
                break
    return class_names


def extract_cardinality_from_restriction(
    g: rdflib.Graph, restriction: BNode, OWL: rdflib.Namespace
) -> Optional[int]:
    """Extract cardinality value from an OWL restriction (returns int or None)"""
    # Check for exact cardinality
    for cardinality_val in g.objects(restriction, OWL.cardinality):
        try:
            return int(str(cardinality_val))
        except (ValueError, TypeError):
            pass

    # Check for minCardinality
    min_card = None
    for min_card_val in g.objects(restriction, OWL.minCardinality):
        try:
            min_card = int(str(min_card_val))
        except (ValueError, TypeError):
            pass

    # Check for maxCardinality
    max_card = None
    for max_card_val in g.objects(restriction, OWL.maxCardinality):
        try:
            max_card = int(str(max_card_val))
        except (ValueError, TypeError):
            pass

    # If we have minCardinality > 1 or maxCardinality > 1, return that value
    if min_card is not None and min_card > 1:
        return min_card
    if max_card is not None and max_card > 1:
        return max_card

    # If minCardinality is 0 or 1 and maxCardinality is None or > 1, return None (unspecified)
    return None


def extract_classes_with_cardinality_from_intersection(
    g: rdflib.Graph,
    intersection_node: BNode,
    classes: Dict[str, ClassInfo],
    OWL: rdflib.Namespace,
) -> Dict[str, Optional[int]]:
    """Extract classes with their cardinalities from an owl:intersectionOf construct"""
    class_cardinalities: Dict[str, Optional[int]] = {}

    try:
        collection = Collection(g, intersection_node)
        for item in collection:
            if isinstance(item, BNode):
                # Check for owl:onClass with cardinality
                on_class = list(g.objects(item, OWL.onClass))
                if on_class:
                    cardinality = extract_cardinality_from_restriction(g, item, OWL)
                    for cls in on_class:
                        if isinstance(cls, rdflib.URIRef):
                            cls_name_on_item: Optional[str] = None
                            if str(cls) in classes:
                                cls_name_on_item = classes[str(cls)].name
                            else:
                                cls_name_on_item = extract_class_name(cls, g)
                            if cls_name_on_item:
                                class_cardinalities[cls_name_on_item] = cardinality

                # Check for allValuesFrom with cardinality
                all_values = list(g.objects(item, OWL.allValuesFrom))
                for val in all_values:
                    if isinstance(val, rdflib.URIRef):
                        cardinality = extract_cardinality_from_restriction(g, item, OWL)
                        cls_name_all: Optional[str] = None
                        if str(val) in classes:
                            cls_name_all = classes[str(val)].name
                        else:
                            cls_name_all = extract_class_name(val, g)
                        if cls_name_all:
                            class_cardinalities[cls_name_all] = cardinality

                # Check for someValuesFrom with cardinality
                some_values = list(g.objects(item, OWL.someValuesFrom))
                for val in some_values:
                    if isinstance(val, rdflib.URIRef):
                        cardinality = extract_cardinality_from_restriction(g, item, OWL)
                        cls_name_some: Optional[str] = None
                        if str(val) in classes:
                            cls_name_some = classes[str(val)].name
                        else:
                            cls_name_some = extract_class_name(val, g)
                        if cls_name_some:
                            class_cardinalities[cls_name_some] = cardinality
    except Exception:
        # Fallback: manual list traversal
        current = intersection_node
        while current and current != rdflib.RDF.nil:
            first = list(g.objects(current, rdflib.RDF.first))
            rest = list(g.objects(current, rdflib.RDF.rest))

            if first:
                first_item = first[0]
                if isinstance(first_item, BNode):
                    # Check for owl:onClass with cardinality
                    on_class = list(g.objects(first_item, OWL.onClass))
                    if on_class:
                        cardinality = extract_cardinality_from_restriction(
                            g, first_item, OWL
                        )
                        for cls in on_class:
                            if isinstance(cls, rdflib.URIRef):
                                cls_name_on2: Optional[str] = None
                                if str(cls) in classes:
                                    cls_name_on2 = classes[str(cls)].name
                                else:
                                    cls_name_on2 = extract_class_name(cls, g)
                                if cls_name_on2:
                                    class_cardinalities[cls_name_on2] = cardinality

                    # Check for allValuesFrom with cardinality
                    all_values = list(g.objects(first_item, OWL.allValuesFrom))
                    for val in all_values:
                        if isinstance(val, rdflib.URIRef):
                            cardinality = extract_cardinality_from_restriction(
                                g, first_item, OWL
                            )
                            cls_name_all2: Optional[str] = None
                            if str(val) in classes:
                                cls_name_all2 = classes[str(val)].name
                            else:
                                cls_name_all2 = extract_class_name(val, g)
                            if cls_name_all2:
                                class_cardinalities[cls_name_all2] = cardinality

                    # Check for someValuesFrom with cardinality
                    some_values = list(g.objects(first_item, OWL.someValuesFrom))
                    for val in some_values:
                        if isinstance(val, rdflib.URIRef):
                            cardinality = extract_cardinality_from_restriction(
                                g, first_item, OWL
                            )
                            cls_name_some2: Optional[str] = None
                            if str(val) in classes:
                                cls_name_some2 = classes[str(val)].name
                            else:
                                cls_name_some2 = extract_class_name(val, g)
                            if cls_name_some2:
                                class_cardinalities[cls_name_some2] = cardinality

            if rest and rest[0] != rdflib.RDF.nil and isinstance(rest[0], BNode):
                current = rest[0]
            else:
                break

    return class_cardinalities


def extract_restriction_properties(
    g: rdflib.Graph,
    restriction: BNode,
    class_uri: str,
    class_info: ClassInfo,
    classes: Dict[str, ClassInfo],
    OWL: rdflib.Namespace,
):
    """Extract properties from OWL restrictions in rdfs:subClassOf"""
    # Get the property from the restriction
    on_properties = list(g.objects(restriction, OWL.onProperty))
    if not on_properties:
        return

    prop_uri = on_properties[0]
    if isinstance(prop_uri, BNode):
        return  # Skip blank node properties

    prop_name = extract_property_name(prop_uri, g)
    if not prop_name:
        return

    # Get the range classes with their cardinalities from allValuesFrom or someValuesFrom
    range_class_cardinalities: Dict[str, Optional[int]] = {}

    # Get cardinality from the main restriction (applies to all classes if not overridden)
    main_cardinality = extract_cardinality_from_restriction(g, restriction, OWL)

    for range_val in g.objects(restriction, OWL.allValuesFrom):
        if isinstance(range_val, rdflib.URIRef):
            # Direct class reference - use main cardinality
            cls_name_allval: Optional[str] = None
            if str(range_val) in classes:
                cls_name_allval = classes[str(range_val)].name
            else:
                cls_name_allval = extract_class_name(range_val, g)
            if cls_name_allval:
                range_class_cardinalities[cls_name_allval] = main_cardinality
        elif isinstance(range_val, BNode):
            # Check for owl:unionOf
            union_of = list(g.objects(range_val, OWL.unionOf))
            if union_of and isinstance(union_of[0], BNode):
                union_classes = extract_classes_from_union(g, union_of[0], classes)
                for cls_name in union_classes:
                    range_class_cardinalities[cls_name] = main_cardinality
            else:
                # Check for owl:intersectionOf
                intersection_of = list(g.objects(range_val, OWL.intersectionOf))
                if intersection_of and isinstance(intersection_of[0], BNode):
                    # Extract classes with their specific cardinalities from intersection
                    intersection_cardinalities = (
                        extract_classes_with_cardinality_from_intersection(
                            g, intersection_of[0], classes, OWL
                        )
                    )
                    # Merge with main cardinality as fallback
                    for cls_name, card in intersection_cardinalities.items():
                        range_class_cardinalities[cls_name] = (
                            card if card is not None else main_cardinality
                        )

    # If not found in allValuesFrom, check someValuesFrom
    if not range_class_cardinalities:
        for range_val in g.objects(restriction, OWL.someValuesFrom):
            if isinstance(range_val, rdflib.URIRef):
                cls_name_someval: Optional[str] = None
                if str(range_val) in classes:
                    cls_name_someval = classes[str(range_val)].name
                else:
                    cls_name_someval = extract_class_name(range_val, g)
                if cls_name_someval:
                    range_class_cardinalities[cls_name_someval] = main_cardinality
            elif isinstance(range_val, BNode):
                # Check for owl:unionOf
                union_of = list(g.objects(range_val, OWL.unionOf))
                if union_of and isinstance(union_of[0], BNode):
                    union_classes = extract_classes_from_union(g, union_of[0], classes)
                    for cls_name_union in union_classes:
                        range_class_cardinalities[cls_name_union] = main_cardinality
                # Check for owl:intersectionOf in someValuesFrom
                intersection_of = list(g.objects(range_val, OWL.intersectionOf))
                if intersection_of and isinstance(intersection_of[0], BNode):
                    intersection_cardinalities = (
                        extract_classes_with_cardinality_from_intersection(
                            g, intersection_of[0], classes, OWL
                        )
                    )
                    for cls_name_int, card in intersection_cardinalities.items():
                        range_class_cardinalities[cls_name_int] = (
                            card if card is not None else main_cardinality
                        )

    # Also check for owl:onClass (used in some restrictions)
    for on_class in g.objects(restriction, OWL.onClass):
        if isinstance(on_class, rdflib.URIRef):
            cls_name_onclass: Optional[str] = None
            if str(on_class) in classes:
                cls_name_onclass = classes[str(on_class)].name
            else:
                cls_name_onclass = extract_class_name(on_class, g)
            if cls_name_onclass:
                # Use cardinality from this restriction
                range_class_cardinalities[cls_name_onclass] = main_cardinality

    # Create property info if we have a valid property
    if prop_name and range_class_cardinalities:
        # Check if property already exists
        existing_prop = None
        for prop in class_info.properties:
            if prop.name == prop_name:
                existing_prop = prop
                break

        if existing_prop:
            # Merge new classes with their cardinalities
            for cls_name, card in range_class_cardinalities.items():
                # Update if not present or if new cardinality is more specific
                if cls_name not in existing_prop.range_classes:
                    existing_prop.range_classes[cls_name] = card
                elif card is not None and existing_prop.range_classes[cls_name] is None:
                    existing_prop.range_classes[cls_name] = card
        else:
            # Create new property from restriction
            prop_info = PropertyInfo(
                name=prop_name,
                property_type="object",  # Restrictions are typically object properties
                range_classes=range_class_cardinalities,
                description=get_property_description(g, prop_uri),
                required=False,  # Explicitly set to False - restrictions don't imply required
            )
            class_info.properties.append(prop_info)
            class_info.property_uris[prop_name] = str(prop_uri)


def _find_ontology_search_root(ttl_path: Path) -> Path:
    """Find the directory to search for sibling TTL files declaring ontology IRIs.

    Looks for the nearest ancestor named 'ontologies' (so we can search the
    entire subtree across modules/imports/sandbox), or fall back to the TTL
    file's own parent.
    """
    for parent in ttl_path.parents:
        if parent.name == "ontologies":
            return parent
    for parent in ttl_path.parents:
        candidate = parent / "ontologies"
        if candidate.is_dir():
            return candidate
    return ttl_path.parent


def _parse_ttl_cached(ttl_file: Path) -> Optional[rdflib.Graph]:
    """Parse a TTL file once and cache the resulting graph."""
    key = str(ttl_file.resolve())
    if key in _IMPORT_GRAPH_CACHE:
        return _IMPORT_GRAPH_CACHE[key]
    try:
        graph = rdflib.Graph()
        graph.parse(str(ttl_file), format="turtle")
        _IMPORT_GRAPH_CACHE[key] = graph
        return graph
    except Exception:
        _IMPORT_GRAPH_CACHE[key] = None
        return None


def _locator_from_graph(
    graph: rdflib.Graph,
    ontology: rdflib.term.Node,
    ttl_file: Path,
) -> OntologyLocator:
    """Build a locator from an `owl:Ontology` subject's annotations.

    Reads the optional ``abi:pythonPackage`` / ``abi:ontologyResource`` /
    ``abi:pythonResource`` annotations declared on the ontology subject; any
    that are missing simply stay ``None`` so the filesystem fallback applies.
    """
    locator = OntologyLocator(ttl_path=ttl_file)
    for obj in graph.objects(ontology, _ABI_PYTHON_PACKAGE):
        locator.python_package = str(obj).strip()
        break
    for obj in graph.objects(ontology, _ABI_ONTOLOGY_RESOURCE):
        locator.ontology_resource = str(obj).strip()
        break
    for obj in graph.objects(ontology, _ABI_PYTHON_RESOURCE):
        locator.python_resource = str(obj).strip()
        break
    return locator


def _index_ttl_file(
    ttl_file: Path,
    index: Dict[str, OntologyLocator],
    OWL: rdflib.Namespace,
    RDF: rdflib.Namespace,
) -> None:
    """Parse `ttl_file` and add its ontology IRIs (and version IRIs) to `index`."""
    graph = _parse_ttl_cached(ttl_file)
    if graph is None:
        return
    for ontology in graph.subjects(RDF.type, OWL.Ontology):
        if isinstance(ontology, BNode):
            continue
        locator = _locator_from_graph(graph, ontology, ttl_file)
        index.setdefault(str(ontology), locator)
        for version_iri in graph.objects(ontology, OWL.versionIRI):
            if isinstance(version_iri, rdflib.URIRef):
                index.setdefault(str(version_iri), locator)


def _build_ontology_index(
    search_root: Path,
    OWL: rdflib.Namespace,
    RDF: rdflib.Namespace,
) -> Dict[str, OntologyLocator]:
    """Walk `search_root` once and index every ontology IRI it declares.

    A TTL file's "ontology IRIs" are the subjects of `(?, rdf:type, owl:Ontology)`
    plus any `owl:versionIRI` objects on those subjects (so callers can import
    by either the canonical IRI or a versioned form). Locator annotations on
    each ontology are captured at indexing time so resolution can dispatch to
    ``importlib.resources`` when present.
    """
    key = str(search_root.resolve())
    if key in _ONTOLOGY_INDEX_CACHE:
        return _ONTOLOGY_INDEX_CACHE[key]

    index: Dict[str, OntologyLocator] = {}
    for ttl_file in search_root.rglob("*.ttl"):
        _index_ttl_file(ttl_file, index, OWL, RDF)

    _ONTOLOGY_INDEX_CACHE[key] = index
    return index


_WORKSPACE_MARKERS = ("pyproject.toml", ".git", "Makefile")


def _discover_workspace_naas_abi_roots(start: Path) -> List[Path]:
    """Find on-disk ``naas_abi*`` package directories in the surrounding workspace.

    Used as a fallback when a sibling package isn't installed in the current
    venv (e.g. running onto2py from the marketplace's venv against an ontology
    that imports an IRI declared in ``naas-abi``). Walks up from *start*
    through every parent that carries a project marker, and for each scans
    ``libs/*/`` and direct children for ``naas_abi*`` package directories
    (those containing an ``__init__.py``).
    """
    roots: List[Path] = []
    seen: Set[str] = set()
    current = start.resolve()
    if current.is_file():
        current = current.parent
    visited_workspaces: Set[str] = set()
    while True:
        if any((current / m).exists() for m in _WORKSPACE_MARKERS):
            key = str(current)
            if key not in visited_workspaces:
                visited_workspaces.add(key)
                search_dirs = [current, current / "libs"]
                for search_dir in search_dirs:
                    if not search_dir.is_dir():
                        continue
                    for child in search_dir.iterdir():
                        if not child.is_dir():
                            continue
                        # libs/<dist>/<package>/ layout
                        for grandchild in child.iterdir() if child.is_dir() else []:
                            if (
                                grandchild.is_dir()
                                and grandchild.name.startswith("naas_abi")
                                and "-" not in grandchild.name
                                and (grandchild / "__init__.py").exists()
                            ):
                                resolved = str(grandchild.resolve())
                                if resolved not in seen:
                                    seen.add(resolved)
                                    roots.append(grandchild)
                        # Direct child layout
                        if (
                            child.name.startswith("naas_abi")
                            and "-" not in child.name
                            and (child / "__init__.py").exists()
                        ):
                            resolved = str(child.resolve())
                            if resolved not in seen:
                                seen.add(resolved)
                                roots.append(child)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return roots


def _discover_naas_abi_package_roots(
    workspace_hint: Optional[Path] = None,
) -> List[Path]:
    """Return the on-disk roots of every importable `naas_abi*` package.

    Works for both editable checkouts (where each package lives under
    ``libs/<dist>/<package>/``) and wheel installs (where it lives under
    ``site-packages/<package>/``). We rely on ``pkgutil.iter_modules`` so
    discovery doesn't require importing the packages.

    When *workspace_hint* is given (typically the importer's TTL path), the
    surrounding workspace is also scanned filesystem-wise for sibling
    ``naas_abi*`` packages — covers the case where a package is on disk but
    not installed in the current venv.
    """
    roots: List[Path] = []
    seen: Set[str] = set()
    for _finder, name, ispkg in pkgutil.iter_modules():
        if not ispkg or not name.startswith("naas_abi"):
            continue
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            continue
        if spec is None or not spec.submodule_search_locations:
            continue
        for loc in spec.submodule_search_locations:
            resolved = str(Path(loc).resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            roots.append(Path(loc))

    if workspace_hint is not None:
        for extra in _discover_workspace_naas_abi_roots(workspace_hint):
            resolved = str(extra.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            roots.append(extra)

    return roots


def _build_global_ontology_index(
    OWL: rdflib.Namespace,
    RDF: rdflib.Namespace,
    workspace_hint: Optional[Path] = None,
) -> Dict[str, OntologyLocator]:
    """Index every ontology declared inside any installed `naas_abi*` package.

    Built once per process; subsequent calls return the cached dict. The walk
    is opt-in via lookup — callers that resolve a local relative import don't
    pay for it. ``workspace_hint`` extends discovery to on-disk sibling
    packages that aren't installed in the current venv.
    """
    global _GLOBAL_ONTOLOGY_INDEX
    if _GLOBAL_ONTOLOGY_INDEX is not None:
        return _GLOBAL_ONTOLOGY_INDEX

    index: Dict[str, OntologyLocator] = {}
    for root in _discover_naas_abi_package_roots(workspace_hint=workspace_hint):
        for ttl_file in root.rglob("*.ttl"):
            _index_ttl_file(ttl_file, index, OWL, RDF)

    _GLOBAL_ONTOLOGY_INDEX = index
    return index


def _find_ttl_for_ontology(
    ontology_iri: str,
    search_root: Path,
    OWL: rdflib.Namespace,
    RDF: rdflib.Namespace,
) -> Optional[OntologyLocator]:
    """Find a locator for `ontology_iri`.

    Looks first under `search_root` (the importer's local ontology tree), then
    falls back to the global cross-package index so an ontology in package A
    can import an ontology declared in package B by its canonical IRI.
    """
    key = (ontology_iri, str(search_root))
    if key in _IMPORT_FILE_CACHE:
        return _IMPORT_FILE_CACHE[key]

    local = _build_ontology_index(search_root, OWL, RDF)
    found = local.get(ontology_iri.strip())
    if found is None:
        glob = _build_global_ontology_index(OWL, RDF, workspace_hint=search_root)
        found = glob.get(ontology_iri.strip())
    _IMPORT_FILE_CACHE[key] = found
    return found


def _resolve_owl_imports(
    g: rdflib.Graph,
    ttl_file_path: Optional[str],
    OWL: rdflib.Namespace,
    RDF: rdflib.Namespace,
) -> List[Path]:
    """Recursively resolve `owl:imports` declarations into the given graph.

    For each `owl:imports <IRI>` triple, search for a sibling TTL file whose
    declared ontology IRI matches (`<IRI> a owl:Ontology` or `owl:versionIRI`).
    Merge that file's triples into `g` and continue resolving any nested
    imports. Imports we can't locate locally are skipped with a warning.

    Returns the list of TTL files that were merged in (in resolution order).
    """
    if ttl_file_path is None:
        return []

    main_path = Path(ttl_file_path).resolve()
    search_root = _find_ontology_search_root(main_path)

    visited_iris: Set[str] = set()
    merged_files: List[Path] = []
    queue: List[rdflib.Graph] = [g]

    while queue:
        current = queue.pop(0)
        for imp_uri in list(current.objects(None, OWL.imports)):
            imp_str = str(imp_uri)
            if imp_str in visited_iris:
                continue
            visited_iris.add(imp_str)

            locator = _find_ttl_for_ontology(imp_str, search_root, OWL, RDF)
            imp_path = _materialize_locator_ttl(locator) if locator else None
            if imp_path is None:
                print(
                    f"⚠️  onto2py: could not resolve owl:imports <{imp_str}> "
                    f"under {search_root}; skipping"
                )
                continue
            if imp_path.resolve() == main_path:
                continue

            imp_graph = _parse_ttl_cached(imp_path)
            if imp_graph is None:
                continue

            for t in imp_graph:
                g.add(t)
            merged_files.append(imp_path)
            queue.append(imp_graph)

    return merged_files


def _collect_declared_class_uris(
    graph: rdflib.Graph,
    RDF: rdflib.Namespace,
    OWL: rdflib.Namespace,
    RDFS: rdflib.Namespace,
) -> Set[str]:
    """Return the URI strings of non-blank classes declared in `graph`."""
    out: Set[str] = set()
    for cls in graph.subjects(RDF.type, OWL.Class):
        if not isinstance(cls, BNode):
            out.add(str(cls))
    for cls in graph.subjects(RDF.type, RDFS.Class):
        if not isinstance(cls, BNode):
            out.add(str(cls))
    return out


def _collect_declared_property_uris(
    graph: rdflib.Graph,
    RDF: rdflib.Namespace,
    OWL: rdflib.Namespace,
) -> Set[str]:
    """Return the URI strings of non-blank properties declared in `graph`."""
    out: Set[str] = set()
    for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
        if not isinstance(prop, BNode):
            out.add(str(prop))
    for prop in graph.subjects(RDF.type, OWL.DatatypeProperty):
        if not isinstance(prop, BNode):
            out.add(str(prop))
    return out


def _filter_unresolved_range_classes(
    classes: Dict[str, "ClassInfo"],
    properties: Dict[str, "PropertyInfo"],
) -> None:
    """Strip class names from object-property ranges that won't be emitted.

    `range_classes` is keyed by Python class name. When that name does not
    correspond to a class we're emitting in this file, referencing it in a
    `Union[...]` annotation produces a `NameError`/`PydanticUndefinedAnnotation`.
    Drop those keys — the generator always seeds object-property unions with
    `{str, URIRef}` so the resulting annotation stays valid.
    """
    known_class_names: Set[str] = {ci.name for ci in classes.values()}

    def _filter(prop: "PropertyInfo") -> None:
        if prop.property_type != "object":
            return
        for cls_name in list(prop.range_classes.keys()):
            # "URIRef" is a sentinel injected by get_property_range for
            # owl:Class / owl:Thing ranges; always preserve it.
            if cls_name == "URIRef":
                continue
            if cls_name not in known_class_names:
                del prop.range_classes[cls_name]

    for prop_info in properties.values():
        _filter(prop_info)
    for class_info in classes.values():
        for prop_info in class_info.properties:
            _filter(prop_info)


def _collect_external_references(
    main_graph: rdflib.Graph,
    merged_graph: rdflib.Graph,
    main_class_uris: Set[str],
    main_prop_uris: Set[str],
    RDF: rdflib.Namespace,
    OWL: rdflib.Namespace,
    RDFS: rdflib.Namespace,
) -> Tuple[Set[str], Set[str]]:
    """Find classes/properties referenced in `main_graph` but defined in imports.

    A URI counts as "referenced" if it appears as the object of any triple in
    `main_graph` (this naturally covers rdfs:subClassOf, rdfs:domain/range,
    owl:someValuesFrom/allValuesFrom/onClass/onProperty, owl:unionOf list
    members, etc. because blank-node structures live in `main_graph` too).
    """
    external_classes: Set[str] = set()
    external_props: Set[str] = set()

    for _s, _p, obj in main_graph:
        if not isinstance(obj, rdflib.URIRef):
            continue
        obj_str = str(obj)
        if obj_str not in main_class_uris and (
            (obj, RDF.type, OWL.Class) in merged_graph
            or (obj, RDF.type, RDFS.Class) in merged_graph
        ):
            external_classes.add(obj_str)
        if obj_str not in main_prop_uris and (
            (obj, RDF.type, OWL.ObjectProperty) in merged_graph
            or (obj, RDF.type, OWL.DatatypeProperty) in merged_graph
        ):
            external_props.add(obj_str)

    return external_classes, external_props


_FILE_IMPORT_SCHEME = "file://"


def _materialize_locator_ttl(locator: OntologyLocator) -> Optional[Path]:
    """Return a filesystem path for `locator`'s TTL.

    Prefers ``importlib.resources`` when the ontology carries the locator
    annotations — that keeps cross-package imports working in editable
    installs, wheels, and zipped distributions alike. Falls back to the
    discovered on-disk path otherwise.
    """
    if locator.python_package and locator.ontology_resource:
        try:
            traversable = importlib_resources.files(
                locator.python_package
            ).joinpath(locator.ontology_resource)
            with importlib_resources.as_file(traversable) as fs_path:
                return Path(fs_path).resolve()
        except (ModuleNotFoundError, FileNotFoundError):
            pass
    return locator.ttl_path


def _python_module_for_locator(locator: OntologyLocator) -> Optional[str]:
    """Compute the dotted Python module of the generated `.py` for `locator`.

    Uses the explicit ``abi:pythonPackage`` + ``abi:pythonResource``
    annotations when both are present; otherwise returns ``None`` so the
    caller can fall back to path-based derivation.
    """
    if not (locator.python_package and locator.python_resource):
        return None
    resource = locator.python_resource.strip().lstrip("/")
    stem = resource[:-3] if resource.endswith(".py") else resource
    dotted = stem.replace("/", ".").replace("\\", ".")
    return f"{locator.python_package}.{dotted}" if dotted else locator.python_package

# Matches Turtle's `owl:imports <iri>` (and the rare full-IRI form
# `<http://www.w3.org/2002/07/owl#imports> <iri>`). Compact prefixed-name
# imports like `owl:imports myonto:Foo` are not supported — file/python
# paths must be angle-bracketed.
_OWL_IMPORTS_RE = re.compile(
    r"(?:owl:imports|<http://www\.w3\.org/2002/07/owl#imports>)\s*<([^>]+)>",
)


def _quick_extract_owl_imports(content: str) -> List[str]:
    """Find owl:imports IRIs in a TTL string without invoking rdflib.

    Used to compute the cache key before deciding whether to parse. Only
    angle-bracketed IRIs are recognized. TTL line comments (``#`` to EOL)
    are stripped first so example imports inside comments don't fool the
    regex into trying to resolve them.

    ``http(s)://`` IRIs are kept: resolved against the global ontology index
    at resolve time. If no installed package declares the IRI, the import
    is skipped with a warning rather than failing.
    """
    stripped = "\n".join(line.split("#", 1)[0] for line in content.splitlines())
    return _OWL_IMPORTS_RE.findall(stripped)


def _resolve_owl_import(
    iri: str, importer_ttl_path: Optional[Path]
) -> Optional[Tuple[str, str]]:
    """Resolve an ``owl:imports`` IRI to (ttl_content, generated_python_module).

    Supported forms:

    - ``http(s)://<ontology IRI>`` — resolved against an index of every
      ontology declared inside any installed ``naas_abi*`` package. When the
      indexed ontology carries the locator annotations
      (``abi:pythonPackage`` + ``abi:ontologyResource`` /
      ``abi:pythonResource``), the TTL is loaded through
      ``importlib.resources`` and the generated-`.py` module is derived from
      those annotations. Falls back to the on-disk TTL path otherwise.
      Returns ``None`` if no installed package declares the IRI — the caller
      treats this as "skip with warning" so traditional remote-only imports
      (e.g. ``bfo-core.ttl``) don't fail the build.
    - ``file://<absolute path>`` or a plain filesystem path — read directly
      from disk. Relative paths are resolved against the importing TTL's
      directory. The generated Python module is derived by walking up to the
      first ``naas_abi*`` ancestor directory and joining the parts.

    The Python module is *not* the importer's module — it points at the
    already-generated ``.py`` of the imported ontology, so the importer can
    emit ``from <that module> import <ClassName>``.
    """
    if iri.startswith(("http://", "https://")):
        OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
        RDF = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
        if importer_ttl_path is not None:
            search_root = _find_ontology_search_root(
                Path(importer_ttl_path).resolve()
            )
        else:
            search_root = Path.cwd()
        locator = _find_ttl_for_ontology(iri, search_root, OWL, RDF)
        if locator is None:
            return None
        ttl_path = _materialize_locator_ttl(locator)
        if ttl_path is None:
            return None
        content = ttl_path.read_text()
        py_module = _python_module_for_locator(locator) or _path_to_python_module(
            ttl_path
        )
        return content, py_module

    if iri.startswith(_FILE_IMPORT_SCHEME):
        fs_path = Path(iri[len(_FILE_IMPORT_SCHEME):])
    else:
        fs_path = Path(iri)
    if not fs_path.is_absolute() and importer_ttl_path is not None:
        fs_path = Path(importer_ttl_path).parent / fs_path
    fs_path = fs_path.resolve()
    content = fs_path.read_text()
    py_module = _path_to_python_module(fs_path)
    return content, py_module


def _path_to_python_module(ttl_path: Path) -> str:
    """Derive the dotted Python module path of the generated .py sibling.

    Walks up the path to the first ancestor directory whose name starts with
    ``naas_abi`` (the package root convention used across this repo), then
    joins parts to the file's stem. Stops early at any part containing a
    hyphen (e.g. ``naas-abi-core`` distribution dir vs ``naas_abi_core``
    package dir).
    """
    parts = ttl_path.parts
    naas_idx: Optional[int] = None
    for i, part in enumerate(parts):
        if part.startswith("naas_abi") and "-" not in part:
            naas_idx = i
            break
    if naas_idx is None:
        raise ValueError(
            f"Cannot derive Python module path for {ttl_path}: no "
            "naas_abi* ancestor directory found"
        )
    module_parts = list(parts[naas_idx:-1]) + [ttl_path.stem]
    safe_parts: List[str] = []
    for part in module_parts:
        if "-" in part:
            break
        safe_parts.append(part)
    return ".".join(safe_parts)


def _extract_into(
    g: rdflib.Graph,
    classes: Dict[str, ClassInfo],
    properties: Dict[str, PropertyInfo],
) -> None:
    """Run class/property extraction over ``g`` into the given dicts.

    Pre-existing entries in ``classes`` (typically external classes
    populated from owl:imports) are *not* overwritten, and their parent
    chains are not re-resolved. Pre-existing entries in ``properties`` are
    likewise preserved.

    Mirrors the logic the main flow used to inline; factored out so it can
    be applied to imported graphs as well as the importer's graph.
    """
    RDF = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
    SHACL = rdflib.Namespace("http://www.w3.org/ns/shacl#")

    for cls in g.subjects(RDF.type, OWL.Class):
        if isinstance(cls, BNode):
            continue
        if str(cls) in classes:
            continue
        class_name = extract_class_name(cls, g)
        if class_name:
            classes[str(cls)] = ClassInfo(
                name=class_name,
                uri=str(cls),
                parent_classes=[],
                properties=[],
                description=get_description(g, cls),
                label=get_label(g, cls),
            )

    for cls in g.subjects(RDF.type, RDFS.Class):
        if isinstance(cls, BNode):
            continue
        if str(cls) in classes:
            continue
        class_name = extract_class_name(cls, g)
        if class_name:
            classes[str(cls)] = ClassInfo(
                name=class_name,
                uri=str(cls),
                parent_classes=[],
                properties=[],
                description=get_description(g, cls),
                label=get_label(g, cls),
            )

    for cls_uri, class_info in list(classes.items()):
        if class_info.external_module:
            # Externals already have their parent chain baked in.
            continue
        for parent in g.objects(rdflib.URIRef(cls_uri), RDFS.subClassOf):
            if str(parent) in classes:
                parent_name = classes[str(parent)].name
                if parent_name not in class_info.parent_classes:
                    class_info.parent_classes.append(parent_name)
            elif isinstance(parent, BNode):
                restriction_types = list(g.objects(parent, RDF.type))
                if OWL.Restriction in restriction_types:
                    extract_restriction_properties(
                        g, parent, cls_uri, class_info, classes, OWL
                    )

    for prop in g.subjects(RDF.type, OWL.ObjectProperty):
        if str(prop) in properties:
            continue
        prop_name = extract_property_name(prop, g)
        if prop_name:
            properties[str(prop)] = PropertyInfo(
                name=prop_name,
                property_type="object",
                range_classes=get_property_range(g, prop, classes),
                description=get_property_description(g, prop),
            )

    for prop in g.subjects(RDF.type, OWL.DatatypeProperty):
        if str(prop) in properties:
            continue
        prop_name = extract_property_name(prop, g)
        if prop_name:
            properties[str(prop)] = PropertyInfo(
                name=prop_name,
                property_type="data",
                datatype=get_datatype_range(g, prop),
                description=get_property_description(g, prop),
            )

    extract_shacl_constraints(g, classes, properties, SHACL)

    for prop_uri, prop_info in properties.items():
        for domain in g.objects(rdflib.URIRef(prop_uri), RDFS.domain):
            domain_str = str(domain)
            if domain_str not in classes:
                continue
            class_info = classes[domain_str]
            if class_info.external_module:
                # Don't mutate external classes from the importer's graph.
                continue
            existing_props = {prop.name: prop for prop in class_info.properties}
            if prop_info.name in existing_props:
                existing_prop = existing_props[prop_info.name]
                if prop_info.required and existing_prop.required:
                    existing_prop.required = True
                else:
                    existing_prop.required = False
                for cls_name, card in prop_info.range_classes.items():
                    if cls_name not in existing_prop.range_classes:
                        existing_prop.range_classes[cls_name] = card
                    elif (
                        card is not None
                        and existing_prop.range_classes[cls_name] is None
                    ):
                        existing_prop.range_classes[cls_name] = card
                if prop_info.description and not existing_prop.description:
                    existing_prop.description = prop_info.description
                continue
            class_info.properties.append(prop_info)
            class_info.property_uris[prop_info.name] = prop_uri


def _ingest_imported_ontology(
    import_content: str,
    py_module: str,
    classes: Dict[str, ClassInfo],
    properties: Dict[str, PropertyInfo],
) -> None:
    """Parse an imported TTL and add its classes to ``classes`` as externals.

    The imported ontology is fully extracted (including metadata properties
    and inherited properties) so that subclasses defined in the importer can
    inherit the full property set at codegen time. Each new class gets
    ``external_module = py_module`` so the importer's emitter knows to write
    an ``import`` for it instead of a class body.
    """
    import_g = rdflib.Graph()
    import_g.parse(data=import_content, format="turtle")

    sub_classes: Dict[str, ClassInfo] = {}
    sub_properties: Dict[str, PropertyInfo] = {}
    _extract_into(import_g, sub_classes, sub_properties)
    add_metadata_properties(import_g, sub_classes)
    inherit_parent_properties(sub_classes)

    for uri, cinfo in sub_classes.items():
        if uri in classes:
            continue
        cinfo.external_module = py_module
        classes[uri] = cinfo

    for uri, pinfo in sub_properties.items():
        if uri not in properties:
            properties[uri] = pinfo


def onto2py(ttl_file: str | io.TextIOBase, overwrite: bool = False) -> str:
    """
    Convert TTL file to Python classes

    Args:
        ttl_file: Path to TTL file or file-like object
        overwrite: If True, overwrite existing class files. Default is False.

    Returns:
        Generated Python code as string
    """
    ttl_file_path = None
    if isinstance(ttl_file, str):
        ttl_file_path = ttl_file
        with open(ttl_file, "r") as f:
            content = f.read()
        # Validate ontology structure before generating Python.
        # Raises ValueError listing every ERROR-severity issue.
        _run_ontology_check(ttl_file_path)
    else:
        content = ttl_file.read()

    # Cheap pre-scan for owl:imports — avoids the rdflib parse on the common
    # case (no imports) so the cache short-circuit below can still skip all
    # heavy work when the TTL hasn't changed.
    importer_path = Path(ttl_file_path) if ttl_file_path else None
    import_records: List[Tuple[str, str]] = []
    for imported_iri in _quick_extract_owl_imports(content):
        try:
            resolved = _resolve_owl_import(imported_iri, importer_path)
        except Exception as exc:
            raise ValueError(
                f"Failed to resolve owl:imports {imported_iri!r} from "
                f"{ttl_file_path}: {exc}"
            ) from exc
        if resolved is None:
            print(
                f"⚠️  onto2py: could not resolve owl:imports <{imported_iri}> "
                f"from {ttl_file_path}; skipping"
            )
            continue
        import_records.append(resolved)

    # Cache check: hash includes the importer's content AND every imported
    # TTL's content, so any upstream ontology change busts the cache.
    if ttl_file_path is not None and not overwrite:
        hasher = hashlib.sha256()
        hasher.update(content.encode("utf-8"))
        for import_content, _py_module in sorted(import_records):
            hasher.update(b"\x00")
            hasher.update(import_content.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(_CACHE_KEY_VERSION.encode("utf-8"))
        combined_hash = hasher.hexdigest()
        cached_code = _read_cached_python(ttl_file_path, combined_hash)
        if cached_code is not None:
            return cached_code

    g = rdflib.Graph()
    g.parse(data=content, format="turtle")

    # Extract classes and their information
    classes: Dict[str, ClassInfo] = {}
    properties: Dict[str, PropertyInfo] = {}

    # Pre-populate external classes from owl:imports so that the importer's
    # subClassOf resolution can find them in `classes`.
    for import_content, py_module in import_records:
        _ingest_imported_ontology(import_content, py_module, classes, properties)

    # Extract the importer's own classes + properties (skipping any URIs
    # already populated as externals).
    _extract_into(g, classes, properties)

    # Inherit properties from parent classes — works across external parents
    # because they were ingested with full property chains.
    inherit_parent_properties(classes)

    # Add required metadata properties (rdfs:label, dcterms:created,
    # dcterms:creator) to all *local* classes. External classes already had
    # this applied during ingestion.
    local_classes = {
        uri: cinfo
        for uri, cinfo in classes.items()
        if cinfo.external_module is None
    }
    add_metadata_properties(g, local_classes)

    # Drop range classes that point to types we won't emit. This happens when
    # an emitted class (typically pulled in from an import because it's
    # referenced as a property range / restriction value) carries properties
    # whose ranges reach further into the import hierarchy. Without this
    # filter, the generated Python file references undefined type names and
    # Pydantic fails with PydanticUndefinedAnnotation at import time.
    _filter_unresolved_range_classes(classes, properties)

    # Generate Python code
    python_code = generate_python_code(classes, properties)

    # Save the Python code next to the input file if a file path was provided
    if ttl_file_path:
        py_file = Path(ttl_file_path).with_suffix(".py")

        # Embed the combined source hash (importer + all owl:imports content +
        # generator version) so future calls short-circuit only when every
        # input AND the generator's output format are unchanged.
        marker_hasher = hashlib.sha256()
        marker_hasher.update(content.encode("utf-8"))
        for import_content, _py_module in sorted(import_records):
            marker_hasher.update(b"\x00")
            marker_hasher.update(import_content.encode("utf-8"))
        marker_hasher.update(b"\x00")
        marker_hasher.update(_CACHE_KEY_VERSION.encode("utf-8"))
        ttl_hash = marker_hasher.hexdigest()
        python_code_with_marker = (
            f"{_CACHE_MARKER_PREFIX}{ttl_hash}\n{python_code}"
        )

        # Read the existing file if it exists
        if py_file.exists():
            with open(py_file, "r") as f:
                existing_code = f.read()
            if existing_code == python_code_with_marker:
                print(f"✅ {ttl_file_path} already converted to {py_file}")
            else:
                with open(py_file, "w") as f:
                    f.write(python_code_with_marker)
                _run_ruff([str(py_file)])
                print(f"✅ Successfully converted {ttl_file_path} to {py_file}")
        else:
            with open(py_file, "w") as f:
                f.write(python_code_with_marker)
            _run_ruff([str(py_file)])
            print(f"✅ Successfully converted {ttl_file_path} to {py_file}")

        # Create individual class files
        create_class_files(ttl_file_path, classes, py_file, overwrite)

    return python_code


def _read_cached_python(ttl_file_path: str, ttl_hash: str) -> Optional[str]:
    """Return cached .py content if it was generated from the same TTL hash.

    The cache marker is written near the top of the generated .py file. We
    look for it within the first handful of lines so a formatter (ruff) is
    free to add a blank line or shuffle imports without invalidating cache.
    """
    py_file = Path(ttl_file_path).with_suffix(".py")
    if not py_file.exists():
        return None
    expected = f"{_CACHE_MARKER_PREFIX}{ttl_hash}"
    try:
        with open(py_file, "r") as f:
            content = f.read()
    except OSError:
        return None
    head = content.split("\n", 10)[:10]
    for line in head:
        if line.strip() == expected:
            return content
    return None


def get_label(g: rdflib.Graph, resource) -> Optional[str]:
    """Get rdfs:label for a resource"""
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")

    for label in g.objects(resource, RDFS.label):
        return str(label)

    return None


def get_description(g: rdflib.Graph, resource) -> Optional[str]:
    """Get description/comment for a resource"""
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")

    for comment in g.objects(resource, RDFS.comment):
        return str(comment)

    for label in g.objects(resource, RDFS.label):
        return str(label)

    return None


def get_property_description(g: rdflib.Graph, prop) -> Optional[str]:
    """Get skos:definition for a property"""
    SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")

    for definition in g.objects(prop, SKOS.definition):
        definition_str = str(definition)
        # Remove language tag if present (e.g., "definition"@en -> "definition")
        if "@" in definition_str:
            definition_str = definition_str.split("@")[0]
        return definition_str

    return None


def get_property_range(
    g: rdflib.Graph, prop, classes: Dict[str, ClassInfo]
) -> Dict[str, Optional[int]]:
    """Get the range classes with cardinalities for an object property"""
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")

    # OWL/RDFS meta-classes are not user-defined Python classes. A range of
    # `owl:Class` means "the value is a class IRI" — model as URIRef|str.
    # Mapping to "URIRef" is a no-op in the emitted union (already seeded
    # with {"str", "URIRef"}) but preserves the cardinality entry that
    # drives list-vs-scalar emission.
    meta_classes = {
        str(OWL.Class),
        str(OWL.Thing),
        str(RDFS.Class),
        str(RDFS.Resource),
    }

    range_classes: Dict[str, Optional[int]] = {}

    for range_cls in g.objects(prop, RDFS.range):
        range_uri = str(range_cls)
        if range_uri in meta_classes:
            range_classes["URIRef"] = None
            continue

        cls_name: Optional[str] = None
        if range_uri in classes:
            cls_name = classes[range_uri].name
            # No cardinality specified in rdfs:range, so use None
            if cls_name:
                range_classes[cls_name] = None
        else:
            cls_name = extract_class_name(range_cls, g)
            if cls_name:
                range_classes[cls_name] = None

    return range_classes


def get_datatype_range(g: rdflib.Graph, prop) -> Optional[str]:
    """Get the datatype range for a data property"""
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    XSD = rdflib.Namespace("http://www.w3.org/2001/XMLSchema#")

    datatype_mapping = {
        str(XSD.string): "str",
        str(XSD.integer): "int",
        str(XSD.int): "int",
        str(XSD.float): "float",
        str(XSD.double): "float",
        str(XSD.boolean): "bool",
        str(XSD.date): "datetime.date",
        str(XSD.dateTime): "datetime.datetime",
    }

    for range_type in g.objects(prop, RDFS.range):
        return datatype_mapping.get(str(range_type), "Any")

    return "Any"


def extract_shacl_constraints(
    g: rdflib.Graph,
    classes: Dict[str, ClassInfo],
    properties: Dict[str, PropertyInfo],
    SHACL,
):
    """Extract SHACL constraints and apply them to properties"""

    # Find SHACL shapes
    for shape in g.subjects(rdflib.RDF.type, SHACL.NodeShape):
        # Get target class
        for target_class in g.objects(shape, SHACL.targetClass):
            if str(target_class) in classes:
                # Process property shapes
                for prop_shape in g.objects(shape, SHACL.property):
                    process_property_shape(
                        g, prop_shape, classes[str(target_class)], properties, SHACL
                    )


def process_property_shape(
    g: rdflib.Graph,
    prop_shape,
    class_info: ClassInfo,
    properties: Dict[str, PropertyInfo],
    SHACL,
):
    """Process a SHACL property shape"""

    # Get the property path
    for path in g.objects(prop_shape, SHACL.path):
        if str(path) in properties:
            prop_info = properties[str(path)]

            # Check cardinality constraints
            for min_count in g.objects(prop_shape, SHACL.minCount):
                if int(str(min_count)) > 0:
                    prop_info.required = True

            # Update cardinality for all range classes if maxCount is specified
            max_count_val = None
            for max_count in g.objects(prop_shape, SHACL.maxCount):
                max_count_val = int(str(max_count))
                break

            if max_count_val is not None:
                # Update all range classes with the cardinality
                for cls_name in prop_info.range_classes:
                    if max_count_val > 1:
                        prop_info.range_classes[cls_name] = max_count_val
                    else:
                        prop_info.range_classes[cls_name] = 1


def inherit_parent_properties(classes: Dict[str, ClassInfo]):
    """
    Inherit properties from parent classes to child classes.
    Properties inherited from parents are made optional to represent capability links.
    """
    # Create a mapping from class name to class info for easier lookup
    name_to_class = {class_info.name: class_info for class_info in classes.values()}

    def collect_inherited_properties(
        class_info: ClassInfo, visited: Optional[Set[str]] = None
    ) -> List[PropertyInfo]:
        """Recursively collect properties from parent classes"""
        if visited is None:
            visited = set()

        # Avoid infinite recursion in case of circular inheritance
        if class_info.name in visited:
            return []

        visited.add(class_info.name)
        inherited_props = []

        for parent_name in class_info.parent_classes:
            if parent_name in name_to_class:
                parent_class = name_to_class[parent_name]

                # Add direct properties from parent (preserve their required status)
                for prop in parent_class.properties:
                    # Create a copy of the property preserving the original required status
                    inherited_prop = PropertyInfo(
                        name=prop.name,
                        property_type=prop.property_type,
                        range_classes=prop.range_classes.copy(),
                        datatype=prop.datatype,
                        required=prop.required,  # Preserve original required status
                        description=prop.description,
                    )
                    inherited_props.append(inherited_prop)

                # Recursively collect from grandparents
                inherited_props.extend(
                    collect_inherited_properties(parent_class, visited.copy())
                )

        return inherited_props

    # Apply inheritance to each class
    for class_info in classes.values():
        inherited_props = collect_inherited_properties(class_info)

        # Add inherited properties that don't already exist
        existing_prop_names = {prop.name for prop in class_info.properties}

        for inherited_prop in inherited_props:
            if inherited_prop.name not in existing_prop_names:
                class_info.properties.append(inherited_prop)

                # Find the property URI from the inheritance chain
                def find_property_uri(
                    prop_name: str,
                    current_class: ClassInfo,
                    search_visited: Optional[Set[str]] = None,
                ) -> Optional[str]:
                    if search_visited is None:
                        search_visited = set()

                    if current_class.name in search_visited:
                        return None
                    search_visited.add(current_class.name)

                    # Check if current class has the property URI
                    if prop_name in current_class.property_uris:
                        return current_class.property_uris[prop_name]

                    # Search in parent classes
                    for parent_name in current_class.parent_classes:
                        if parent_name in name_to_class:
                            parent_class = name_to_class[parent_name]
                            uri = find_property_uri(
                                prop_name, parent_class, search_visited.copy()
                            )
                            if uri:
                                return uri
                    return None

                prop_uri = find_property_uri(inherited_prop.name, class_info)
                if prop_uri:
                    class_info.property_uris[inherited_prop.name] = prop_uri
                existing_prop_names.add(inherited_prop.name)


def add_metadata_properties(g: rdflib.Graph, classes: Dict[str, ClassInfo]):
    """Add required metadata properties (dcterms:created, dcterms:creator) to all classes"""
    from rdflib.namespace import DCTERMS, RDFS

    # Extract property names
    label_prop_name = extract_property_name(RDFS.label, g)
    if not label_prop_name:
        label_prop_name = "label"

    created_prop_name = extract_property_name(DCTERMS.created, g)
    if not created_prop_name:
        created_prop_name = "created"

    creator_prop_name = extract_property_name(DCTERMS.creator, g)
    if not creator_prop_name:
        creator_prop_name = "creator"

    label_prop_uri = str(RDFS.label)
    created_prop_uri = str(DCTERMS.created)
    creator_prop_uri = str(DCTERMS.creator)

    # Add these properties to all classes if they don't already exist
    for class_info in classes.values():
        existing_prop_names = {prop.name for prop in class_info.properties}

        # Add rdfs:label (data property - string) - mandatory
        if label_prop_name not in existing_prop_names:
            label_prop = PropertyInfo(
                name=label_prop_name,
                property_type="data",
                datatype="str",
                description="Label of the resource.",
                required=False,  # Mandatory property
            )
            class_info.properties.append(label_prop)
            class_info.property_uris[label_prop_name] = label_prop_uri

        # Add dcterms:created (data property - date/time) - mandatory
        if created_prop_name not in existing_prop_names:
            created_prop = PropertyInfo(
                name=created_prop_name,
                property_type="data",
                datatype="datetime.datetime",
                description="Date of creation of the resource.",
                default_value="datetime.datetime.now()",
                required=False,  # Mandatory property with default
            )
            class_info.properties.append(created_prop)
            class_info.property_uris[created_prop_name] = created_prop_uri

        # Add dcterms:creator (object property - Agent) - mandatory
        if creator_prop_name not in existing_prop_names:
            creator_prop = PropertyInfo(
                name=creator_prop_name,
                property_type="data",
                range_classes={"str": 1},
                description="An entity responsible for making the resource.",
                default_value='os.environ.get("USER")',
                required=False,  # Mandatory property with default
            )
            class_info.properties.append(creator_prop)
            class_info.property_uris[creator_prop_name] = creator_prop_uri


def create_class_files(
    ttl_file_path: str,
    classes: Dict[str, ClassInfo],
    py_file: Path,
    overwrite: bool = False,
):
    """
    Create individual Python files for each class in the ontology.

    Args:
        ttl_file_path: Path to the original TTL file
        classes: Dictionary of class URIs to ClassInfo objects
        py_file: Path to the generated Python file containing all classes
        overwrite: If True, overwrite existing files. Default is False.
    """
    # Extract module name from the TTL file path
    # Find the directory containing 'ontologies' and use the parent as module base
    ttl_path = Path(ttl_file_path).resolve()
    parts = ttl_path.parts

    # Find 'ontologies' in the path and get the parent directory
    module_base_path = None
    for i, part in enumerate(parts):
        if part == "ontologies" and i > 0:
            # Get the path up to (but not including) 'ontologies'
            module_base_path = Path(*parts[:i])
            break

    if not module_base_path:
        # Fallback: use the parent directory of the TTL file's parent
        module_base_path = ttl_path.parent.parent

    # Create base directory for class files: module_base_path/ontologies/classes/
    base_classes_dir = module_base_path / "ontologies" / "classes"

    # Calculate relative import path from class file to the generated Python file
    # We need to find the relative path from the class file location to the py_file
    py_file_path = py_file.resolve()

    created_count = 0
    skipped_count = 0
    created_files: list[str] = []

    for class_uri, class_info in classes.items():
        # External classes already live in another module's class-files
        # tree; don't redirect them.
        if class_info.external_module:
            continue
        # Parse URI: remove "http://" or "https://" prefix and split by "/"
        uri_str = str(class_uri)
        if uri_str.startswith("http://"):
            uri_str = uri_str[7:]  # Remove "http://"
        elif uri_str.startswith("https://"):
            uri_str = uri_str[8:]  # Remove "https://"

        # Remove "www." if present
        if uri_str.startswith("www."):
            uri_str = uri_str[4:]  # Remove "www."

        # Split by "/" to get path components
        uri_parts = [part for part in uri_str.split("/") if part]
        # Ensure generated folder names are valid Python package segments.
        # Ontology domains commonly contain dots (e.g., ontology.naas.ai).
        uri_parts = [part.replace(".", "_") for part in uri_parts]

        if not uri_parts:
            continue

        # Create directory structure: base_classes_dir/uri_parts[0]/uri_parts[1]/...
        class_dir = base_classes_dir
        for part in uri_parts[:-1]:  # All parts except the last
            class_dir = class_dir / part

        # Create directory if it doesn't exist
        class_dir.mkdir(parents=True, exist_ok=True)

        # File name is the class name in Python
        class_file = class_dir / f"{class_info.name}.py"

        # Skip if file exists and overwrite is False
        if class_file.exists() and not overwrite:
            skipped_count += 1
            continue

        # Calculate import path using absolute import starting from folder that begins with "naas_abi"
        # Stop before any folder with "-" in its name
        py_file_abs = py_file_path.resolve()

        # Find the folder that starts with "naas_abi" in the path
        naas_abi_idx = None
        for i, part in enumerate(py_file_abs.parts):
            if part.startswith("naas_abi"):
                naas_abi_idx = i
                break

        if naas_abi_idx is not None:
            # Build absolute import path from naas_abi folder onwards
            import_parts = list(py_file_abs.parts[naas_abi_idx:-1]) + [
                py_file_path.stem
            ]

            # Stop before any folder with "-" in its name
            filtered_parts = []
            for part in import_parts:
                if "-" in part:
                    # Stop here, use relative import from this point
                    break
                filtered_parts.append(part)

            if len(filtered_parts) < len(import_parts):
                # We stopped early due to hyphen, need to use relative import
                try:
                    class_dir_parent = class_dir.parent
                    rel_path = Path(
                        os.path.relpath(py_file_path.parent, class_dir_parent)
                    )
                    up_levels = rel_path.parts.count("..")
                    remaining_parts = [
                        p for p in rel_path.parts if p not in ("..", ".")
                    ]
                    if remaining_parts:
                        import_path = (
                            "." * (up_levels + 1)
                            + ".".join(remaining_parts)
                            + "."
                            + py_file_path.stem
                        )
                    else:
                        import_path = "." * (up_levels + 1) + py_file_path.stem
                except (ValueError, AttributeError):
                    # Last resort: use relative import based on depth
                    import_path = f"..{'.' * (len(uri_parts) + 1)}{py_file_path.stem}"
            else:
                # No hyphen found, use absolute import
                import_path = ".".join(filtered_parts)
        else:
            # No naas_abi folder found, try relative import
            try:
                class_dir_parent = class_dir.parent
                rel_path = Path(os.path.relpath(py_file_path.parent, class_dir_parent))
                up_levels = rel_path.parts.count("..")
                remaining_parts = [p for p in rel_path.parts if p not in ("..", ".")]
                if remaining_parts:
                    import_path = (
                        "." * (up_levels + 1)
                        + ".".join(remaining_parts)
                        + "."
                        + py_file_path.stem
                    )
                else:
                    import_path = "." * (up_levels + 1) + py_file_path.stem
            except (ValueError, AttributeError):
                # Last resort: use a simple relative import
                import_path = f"..{'.' * (len(uri_parts) + 1)}{py_file_path.stem}"

        # Generate the class file content
        class_file_content = f'''from {import_path} import (
    {class_info.name} as _{class_info.name},
)


class {class_info.name}(_{class_info.name}):
    """Action class for {class_info.name}"""

    def actions(self):
        """Action method - implement your logic here"""
        pass
'''

        # Write the file
        try:
            with open(class_file, "w") as f:
                f.write(class_file_content)
            created_files.append(str(class_file))
            created_count += 1
        except Exception as e:
            print(f"⚠️  Warning: Failed to create class file {class_file}: {e}")

    # Lint all created class files in one batch
    _run_ruff(created_files)

    if created_count > 0 or skipped_count > 0:
        print(
            f"📁 Created {created_count} class file(s), skipped {skipped_count} existing file(s)"
        )


def _find_ruff() -> Optional[str]:
    """Locate the ruff binary, trying several common locations."""
    candidates = [
        "ruff",
        str(Path(sys.executable).parent / "ruff"),
        "uvx ruff",
    ]
    for candidate in candidates:
        parts = candidate.split()
        try:
            result = subprocess.run(
                [*parts, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            continue
    return None


def _run_ruff(paths: list[str]) -> None:
    """Run ruff fix-all + organize-imports + format on the given file paths.

    Mirrors the editor settings:
      source.fixAll        -> ruff check --fix
      source.organizeImports -> ruff check --fix --extend-select I
      editor.formatOnSave  -> ruff format
    """
    if not paths:
        return
    ruff = _find_ruff()
    if ruff is None:
        return
    ruff_parts = ruff.split()
    try:
        subprocess.run(
            [*ruff_parts, "check", "--fix", "--extend-select", "I", *paths],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        subprocess.run(
            [*ruff_parts, "format", *paths],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        pass
    except Exception:
        pass


def apply_linting(code: str) -> str:
    """Apply ruff fix-all, organize-imports, and formatting to generated code."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_file:
            tmp_file.write(code)
            tmp_path = tmp_file.name

        try:
            _run_ruff([tmp_path])

            with open(tmp_path, "r") as f:
                formatted_code = f.read()

            return formatted_code
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return code
    except Exception:
        return code


def generate_python_code(
    classes: Dict[str, ClassInfo], properties: Dict[str, PropertyInfo]
) -> str:
    """Generate Python code from extracted class and property information"""

    # Determine which imports are needed
    needs_any = False
    needs_datetime = False
    needs_os = False

    # Check all properties to see what types are needed
    for class_info in classes.values():
        for prop in class_info.properties:
            if (prop.property_type == "data" and not prop.datatype) or (
                prop.property_type == "object" and not prop.range_classes
            ):
                needs_any = True
            if (
                prop.property_type == "data"
                and prop.datatype
                and "datetime" in prop.datatype
            ):
                needs_datetime = True
            if prop.default_value and "os.environ" in prop.default_value:
                needs_os = True

    # Build typing imports. `List` and `Union` are referenced at runtime by
    # RDFEntity helpers regardless of whether any individual class declares
    # them, so they are always imported.
    typing_imports = [
        "Annotated",
        "Any",
        "Callable",
        "ClassVar",
        "Iterable",
        "List",
        "Optional",
        "Union",
        "get_args",
        "get_origin",
    ]

    # Build sorted stdlib imports
    stdlib_lines: list[str] = ["import uuid"]
    if needs_datetime:
        stdlib_lines.append("import datetime")
    if needs_os:
        stdlib_lines.append("import os")
    stdlib_lines.sort()

    # Build multi-line typing import block
    typing_block = ["from typing import ("] + [
        f"    {name}," for name in sorted(typing_imports)
    ] + [")"]

    code_lines: list[str] = (
        ["from __future__ import annotations", ""]
        + stdlib_lines
        + typing_block
        + [
            "",
            "from pydantic import BaseModel, Field, ValidationError",
            "from rdflib import Graph, Literal, Namespace, URIRef",
            "from rdflib.namespace import OWL, RDF, RDFS, XSD",
        ]
    )

    # Emit `from <module> import <Class>` for every external class brought
    # in via owl:imports. Grouped by module and deduped to keep the import
    # block stable across runs.
    external_by_module: Dict[str, Set[str]] = {}
    for class_info in classes.values():
        if class_info.external_module:
            external_by_module.setdefault(
                class_info.external_module, set()
            ).add(class_info.name)
    for module_path in sorted(external_by_module):
        names = ", ".join(sorted(external_by_module[module_path]))
        code_lines.append(f"from {module_path} import {names}")

    code_lines.extend(
        [
            "",
            'BFO = Namespace("http://purl.obolibrary.org/obo/")',
            'ABI = Namespace("http://ontology.naas.ai/abi/")',
            'CCO = Namespace("https://www.commoncoreontologies.org/")',
            "",
            "",
            "# Base class for all RDF entities",
            "class RDFEntity(BaseModel):",
            '    """Base class for all RDF entities with URI and namespace management"""',
            "",
            '    _namespace: ClassVar[str] = "http://ontology.naas.ai/abi/"',
            '    _uri: str = ""',
            "    _object_properties: ClassVar[set[str]] = set()",
            "    _query_executor: ClassVar[Callable[[str], Iterable[object]] | None] = None",
            "",
            '    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}',
            "",
            "    def __init__(self, **kwargs):",
            '        uri = kwargs.pop("_uri", None)',
            "        super().__init__(**kwargs)",
            "        if uri is not None:",
            "            self._uri = uri",
            "        elif not self._uri:",
            '            self._uri = f"{self._namespace}{uuid.uuid4()}"',
            "",
            "    @classmethod",
            "    def set_namespace(cls, namespace: str):",
            '        """Set the namespace for generating URIs"""',
            "        cls._namespace = namespace",
            "",
            "    @classmethod",
            "    def set_query_executor(",
            "        cls, query_executor: Callable[[str], Iterable[object]] | None",
            "    ):",
            '        """Set the SPARQL query executor used by from_iri()."""',
            "        cls._query_executor = query_executor",
            "",
            "    @staticmethod",
            "    def _extract_result_value(row: object, key: str) -> object | None:",
            '        """Extract a SPARQL binding value from a ResultRow-like object."""',
            "        if hasattr(row, key):",
            "            return getattr(row, key)",
            "        try:",
            "            return row[key]  # type: ignore[index]",
            "        except Exception:",
            "            pass",
            "",
            '        labels = getattr(row, "labels", None)',
            "        if labels and key in labels:",
            "            try:",
            "                return row[key]  # type: ignore[index]",
            "            except Exception:",
            "                pass",
            "",
            "        if isinstance(row, (list, tuple)):",
            '            idx = 0 if key == "p" else 1',
            "            if len(row) > idx:",
            "                return row[idx]",
            "",
            "        return None",
            "",
            "    @staticmethod",
            "    def _coerce_rdf_value(value: object, is_object_property: bool) -> object:",
            '        """Convert RDFLib values to python values used by generated models."""',
            "        if value is None:",
            "            return None",
            "        if is_object_property:",
            "            return str(value)",
            "        if isinstance(value, Literal):",
            "            return value.toPython()",
            "        return str(value)",
            "",
            "    @staticmethod",
            "    def _field_expects_list(field_annotation: object) -> bool:",
            '        """Return True when a field annotation contains a list type."""',
            "        origin = get_origin(field_annotation)",
            "        if origin in (list, List):",
            "            return True",
            "        if origin is Annotated:",
            "            args = get_args(field_annotation)",
            "            if args:",
            "                return RDFEntity._field_expects_list(args[0])",
            "            return False",
            "        if origin is Union:",
            "            return any(",
            "                RDFEntity._field_expects_list(arg)",
            "                for arg in get_args(field_annotation)",
            "                if arg is not type(None)",
            "            )",
            "        return False",
            "",
            "    @staticmethod",
            "    def _fallback_label_from_iri(iri: str) -> str:",
            '        """Build a best-effort label from an IRI."""',
            '        trimmed = iri.rstrip("/")',
            '        if "#" in trimmed:',
            '            return trimmed.split("#")[-1] or trimmed',
            '        return trimmed.split("/")[-1] or trimmed',
            "",
            "    @classmethod",
            "    def from_iri(",
            "        cls,",
            "        iri: str,",
            "        query_executor: Callable[[str], Iterable[object]] | None = None,",
            "        graph_name: str | None = None,",
            "    ):",
            '        """Load a class instance from an IRI using SPARQL query results."""',
            "        iri = str(iri).strip()",
            "        if not iri:",
            '            raise ValueError("iri must be a non-empty string")',
            '        if "<" in iri or ">" in iri:',
            '            raise ValueError("iri must not contain angle brackets")',
            "        if graph_name is not None:",
            "            graph_name = str(graph_name).strip()",
            "            if not graph_name:",
            "                graph_name = None",
            '            elif "<" in graph_name or ">" in graph_name:',
            '                raise ValueError("graph_name must not contain angle brackets")',
            "",
            "        executor = query_executor or cls._query_executor",
            "        if executor is None:",
            "            raise ValueError(",
            '                "No query executor configured. Pass query_executor to from_iri() "',
            '                "or set it with set_query_executor()."',
            "            )",
            "",
            "        if graph_name:",
            '            sparql_query = f"""',
            "                SELECT ?p ?o",
            "                WHERE {{",
            "                    GRAPH <{graph_name}> {{",
            "                        <{iri}> ?p ?o .",
            "                        FILTER(?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)",
            "                    }}",
            "                }}",
            '            """',
            "        else:",
            '            sparql_query = f"""',
            "                SELECT ?p ?o",
            "                WHERE {{",
            "                    <{iri}> ?p ?o .",
            "                    FILTER(?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)",
            "                }}",
            '            """',
            "",
            "        results = executor(sparql_query)",
            "        reverse_property_uris = {",
            "            prop_uri: prop_name",
            '            for prop_name, prop_uri in getattr(cls, "_property_uris", {}).items()',
            "        }",
            '        object_props: set[str] = getattr(cls, "_object_properties", set())',
            '        model_fields = getattr(cls, "model_fields", {})',
            "        values: dict[str, Any] = {}",
            "",
            "        for row in results:  # type: ignore[assignment]",
            '            predicate = cls._extract_result_value(row, "p")',
            '            obj = cls._extract_result_value(row, "o")',
            "            if predicate is None:",
            "                continue",
            "            prop_name = reverse_property_uris.get(str(predicate))",
            "            if not prop_name:",
            "                continue",
            "",
            "            coerced = cls._coerce_rdf_value(",
            "                obj,",
            "                is_object_property=prop_name in object_props,",
            "            )",
            "            field_info = model_fields.get(prop_name)",
            "            expects_list = False",
            "            if field_info is not None:",
            "                expects_list = cls._field_expects_list(field_info.annotation)",
            "",
            "            if prop_name not in values:",
            "                if expects_list:",
            "                    values[prop_name] = [coerced]",
            "                else:",
            "                    values[prop_name] = coerced",
            "            else:",
            "                existing = values[prop_name]",
            "                if isinstance(existing, list):",
            "                    existing.append(coerced)",
            "                elif expects_list:",
            "                    values[prop_name] = [existing, coerced]",
            "                else:",
            "                    values[prop_name] = existing",
            "",
            '        if "label" in model_fields and "label" not in values:',
            '            values["label"] = cls._fallback_label_from_iri(iri)',
            "",
            "        for field_name, field_info in model_fields.items():",
            "            if field_name in values:",
            "                continue",
            "            if field_info.is_required():",
            "                if cls._field_expects_list(field_info.annotation):",
            "                    values[field_name] = []",
            "                else:",
            "                    values[field_name] = None",
            "",
            "        try:",
            "            return cls(_uri=iri, **values)",
            "        except ValidationError:",
            "            # Keep loading permissive for partially populated RDF resources.",
            "            return cls.model_construct(",
            "                _fields_set=set(values.keys()), _uri=iri, **values",
            "            )",
            "",
            "    def rdf(",
            "        self, subject_uri: str | None = None, visited: set[str] | None = None",
            "    ) -> Graph:",
            '        """Generate RDF triples for this instance',
            "",
            "        Args:",
            "            subject_uri: Optional URI to use as subject (defaults to self._uri)",
            "            visited: Set of URIs that have already been processed (for cycle detection)",
            '        """',
            "        # Initialize visited set if not provided",
            "        if visited is None:",
            "            visited = set()",
            "",
            "        g = Graph()",
            '        g.bind("cco", CCO)',
            '        g.bind("bfo", BFO)',
            '        g.bind("abi", ABI)',
            '        g.bind("rdfs", RDFS)',
            '        g.bind("rdf", RDF)',
            '        g.bind("owl", OWL)',
            '        g.bind("xsd", XSD)',
            "",
            "        # Use stored URI or provided subject_uri",
            "        if subject_uri is None:",
            "            subject_uri = self._uri",
            "        subject = URIRef(subject_uri)",
            "",
            "        # Check if we've already processed this entity (cycle detection)",
            "        if subject_uri in visited:",
            "            # Already processed, just return empty graph to avoid infinite recursion",
            "            # The relationship triple will be added by the caller",
            "            return g",
            "",
            "        # Mark this entity as visited before processing",
            "        visited.add(subject_uri)",
            "",
            "        # Add class type",
            '        if hasattr(self, "_class_uri"):',
            "            g.add((subject, RDF.type, URIRef(self._class_uri)))",
            "",
            "        # Add owl:NamedIndividual type",
            "        g.add((subject, RDF.type, OWL.NamedIndividual))",
            "",
            "        # Add label if it exists",
            '        if hasattr(self, "label"):',
            "            g.add((subject, RDFS.label, Literal(self.label)))",
            "",
            '        object_props: set[str] = getattr(self, "_object_properties", set())',
            "",
            "        # Add properties",
            '        if hasattr(self, "_property_uris"):',
            "            for prop_name, prop_uri in self._property_uris.items():",
            "                is_object_prop = prop_name in object_props",
            "                prop_value = getattr(self, prop_name, None)",
            "                if prop_value is not None:",
            "                    if isinstance(prop_value, list):",
            "                        for item in prop_value:",
            '                            if hasattr(item, "rdf") and hasattr(item, "_uri"):',
            "                                # Check if this entity was already visited to prevent cycles",
            "                                if item._uri not in visited:",
            "                                    # Add triples from related object",
            "                                    g += item.rdf(visited=visited)",
            "                                # Always add the triple, even if already visited",
            "                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))",
            "                            elif is_object_prop and isinstance(item, (str, URIRef)):",
            "                                g.add((subject, URIRef(prop_uri), URIRef(str(item))))",
            "                            else:",
            "                                g.add((subject, URIRef(prop_uri), Literal(item)))",
            '                    elif hasattr(prop_value, "rdf") and hasattr(prop_value, "_uri"):',
            "                        # Check if this entity was already visited to prevent cycles",
            "                        if prop_value._uri not in visited:",
            "                            # Add triples from related object",
            "                            g += prop_value.rdf(visited=visited)",
            "                        # Always add the triple, even if already visited",
            "                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))",
            "                    elif is_object_prop and isinstance(prop_value, (str, URIRef)):",
            "                        g.add((subject, URIRef(prop_uri), URIRef(str(prop_value))))",
            "                    else:",
            "                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))",
            "",
            "        return g",
            "",
            "",
        ]
    )

    # Sort classes to handle inheritance properly
    sorted_classes = topological_sort_classes(classes)

    # External classes are imported, not defined — skip emitting bodies or
    # model_rebuild() calls for them. Their RDFEntity base lives in their
    # own generated module.
    locally_defined_classes = [
        c for c in sorted_classes if c.external_module is None
    ]

    for class_info in locally_defined_classes:
        code_lines.extend(generate_class_code(class_info, needs_any))
        code_lines.append("")
        code_lines.append("")

    # Add model_rebuild() calls for forward references
    code_lines.append("# Rebuild models to resolve forward references")
    for class_info in locally_defined_classes:
        code_lines.append(f"{class_info.name}.model_rebuild()")
    code_lines.append("")

    code = "\n".join(code_lines)

    # Apply linting/formatting
    code = apply_linting(code)

    return code


def topological_sort_classes(classes: Dict[str, ClassInfo]) -> List[ClassInfo]:
    """Sort classes so that dependencies come before classes that use them"""

    # More aggressive topological sort that prioritizes inheritance dependencies
    # and handles circular dependencies better
    sorted_classes = []
    visited = set()

    def get_inheritance_depth(class_info: ClassInfo, depth=0, visited_in_chain=None):
        """Calculate inheritance depth, handling cycles"""
        if visited_in_chain is None:
            visited_in_chain = set()

        if class_info.name in visited_in_chain:
            return depth  # Cycle detected, return current depth

        if not class_info.parent_classes:
            return depth

        visited_in_chain.add(class_info.name)
        max_parent_depth = depth

        for parent_name in class_info.parent_classes:
            for parent_class in classes.values():
                if parent_class.name == parent_name:
                    parent_depth = get_inheritance_depth(
                        parent_class, depth + 1, visited_in_chain.copy()
                    )
                    max_parent_depth = max(max_parent_depth, parent_depth)
                    break

        return max_parent_depth

    # Sort by inheritance depth first (deepest inheritance last)
    classes_by_depth = [
        (get_inheritance_depth(class_info), class_info)
        for class_info in classes.values()
    ]
    classes_by_depth.sort(key=lambda x: x[0])

    # Then do standard topological sort within each depth level
    def visit(class_info: ClassInfo, temp_visited=None):
        if temp_visited is None:
            temp_visited = set()

        if class_info.name in visited:
            return
        if class_info.name in temp_visited:
            # Circular dependency - add the class anyway to avoid infinite loops
            if class_info not in sorted_classes:
                sorted_classes.append(class_info)
                visited.add(class_info.name)
            return

        temp_visited.add(class_info.name)

        # Visit parent classes first (inheritance dependencies)
        for parent_name in class_info.parent_classes:
            for parent_class in classes.values():
                if parent_class.name == parent_name:
                    visit(parent_class, temp_visited.copy())
                    break

        visited.add(class_info.name)
        sorted_classes.append(class_info)

    # Process classes in order of inheritance depth
    for depth, class_info in classes_by_depth:
        visit(class_info)

    return sorted_classes


def generate_class_code(
    class_info: ClassInfo, has_any_import: bool = False
) -> List[str]:
    """Generate Python code for a single class"""

    lines = []

    # Deduplicate properties by name while merging stricter constraints.
    unique_props: Dict[str, PropertyInfo] = {}
    for prop in class_info.properties:
        if prop.name in unique_props:
            existing = unique_props[prop.name]
            # Only mark as required if BOTH are required (more conservative approach)
            # This prevents properties from restrictions from being incorrectly marked as required
            if prop.required and existing.required:
                existing.required = True
            elif not prop.required and not existing.required:
                existing.required = False
            # If one is required and one isn't, keep it as optional (safer default)
            else:
                existing.required = False
            # Merge range classes
            for cls_name, card in prop.range_classes.items():
                if cls_name not in existing.range_classes:
                    existing.range_classes[cls_name] = card
                elif card is not None and existing.range_classes[cls_name] is None:
                    existing.range_classes[cls_name] = card
            continue
        unique_props[prop.name] = prop

    properties_list = list(unique_props.values())

    # Determine class bases
    if class_info.parent_classes:
        parents = list(class_info.parent_classes)
        if "RDFEntity" not in parents:
            parents.append("RDFEntity")
        lines.append(f"class {class_info.name}({', '.join(parents)}):")
    else:
        lines.append(f"class {class_info.name}(RDFEntity):")

    # Add class docstring if description exists
    if class_info.description:
        lines.append('    """')
        for line in class_info.description.splitlines():
            lines.append(f"    {line}")
        lines.append('    """')

    if class_info.description:
        lines.append("")

    # Add class-specific metadata
    lines.append(f'    _class_uri: ClassVar[str] = "{class_info.uri}"')

    # Add _name property with rdfs:label
    class_label = class_info.label if class_info.label else class_info.name
    class_label_escaped = class_label.replace('"', '\\"')
    lines.append(f'    _name: ClassVar[str] = "{class_label_escaped}"')

    # Add property URI mapping — multi-line when it would exceed the line limit
    LINE_LIMIT = 88
    if class_info.property_uris:
        sorted_items = sorted(class_info.property_uris.items())
        inline = ", ".join(f'"{k}": "{v}"' for k, v in sorted_items)
        single_line = f"    _property_uris: ClassVar[dict] = {{{inline}}}"
        if len(single_line) <= LINE_LIMIT:
            lines.append(single_line)
        else:
            lines.append("    _property_uris: ClassVar[dict] = {")
            for prop_name, prop_uri in sorted_items:
                lines.append(f'        "{prop_name}": "{prop_uri}",')
            lines.append("    }")
    else:
        lines.append("    _property_uris: ClassVar[dict] = {}")

    object_prop_names = sorted(
        {prop.name for prop in properties_list if prop.property_type == "object"}
    )
    if object_prop_names:
        names = ", ".join(f'"{name}"' for name in object_prop_names)
        single_line = f"    _object_properties: ClassVar[set[str]] = {{{names}}}"
        if len(single_line) <= LINE_LIMIT:
            lines.append(single_line)
        else:
            lines.append("    _object_properties: ClassVar[set[str]] = {")
            for name in object_prop_names:
                lines.append(f'        "{name}",')
            lines.append("    }")
    else:
        lines.append("    _object_properties: ClassVar[set[str]] = set()")

    lines.append("")

    # Add properties grouped by type for readability
    data_properties = [prop for prop in properties_list if prop.property_type == "data"]
    object_properties = sorted(
        (prop for prop in properties_list if prop.property_type == "object"),
        key=lambda prop: prop.name,
    )
    other_properties = sorted(
        (
            prop
            for prop in properties_list
            if prop.property_type not in {"data", "object"}
        ),
        key=lambda prop: prop.name,
    )

    property_groups = [
        ("Data properties", data_properties),
        ("Object properties", object_properties),
        ("Other properties", other_properties),
    ]

    emitted_property_group = False
    for group_label, props in property_groups:
        if not props:
            continue
        if emitted_property_group:
            lines.append("")
        lines.append(f"    # {group_label}")
        for prop in props:
            lines.extend(generate_property_code(prop, has_any_import))
        emitted_property_group = True

    if not emitted_property_group:
        lines.append("    pass")

    return lines


def generate_property_code(
    prop: PropertyInfo, has_any_import: bool = False
) -> List[str]:
    """Generate code lines for a single property using Annotated.

    Returns a list of lines already prefixed with 4-space indentation.
    """
    INDENT = "    "
    LINE_LIMIT = 88

    # Determine base type annotation
    if prop.property_type == "object":
        union_type_parts_set = {"str", "URIRef"}
        for class_name in prop.range_classes:
            union_type_parts_set.add(class_name)

        needs_lists = any(
            c is None or c > 1 for c in prop.range_classes.values()
        )
        union_types = ", ".join(sorted(union_type_parts_set))
        base_type = (
            f"List[Union[{union_types}]]" if needs_lists else f"Union[{union_types}]"
        )
    elif prop.property_type == "data" and prop.datatype:
        base_type = prop.datatype
    else:
        base_type = "Any" if has_any_import else "object"

    # Build Field() call
    if prop.description:
        description = prop.description.replace('"', '\\"')
        field_str = f'Field(description="{description}")'
    else:
        field_str = "Field()"

    # Determine default value string (use double quotes)
    if prop.default_value:
        default_str = prop.default_value.replace("'USER'", '"USER"')
    elif not prop.required:
        default_str = "None"
    else:
        default_str = None

    # Build type annotation
    if prop.default_value:
        final_type = f"Annotated[Optional[{base_type}], {field_str}]"
    elif not prop.required:
        final_type = f"Optional[Annotated[{base_type}, {field_str}]]"
    else:
        final_type = f"Annotated[{base_type}, {field_str}]"

    # Assemble single-line version
    assignment = f" = {default_str}" if default_str is not None else ""
    single_line = f"{INDENT}{prop.name}: {final_type}{assignment}"

    if len(single_line) <= LINE_LIMIT:
        return [single_line]

    # Line too long — emit multi-line form
    lines: List[str] = []

    def _field_lines(depth: int) -> List[str]:
        """Return Field(...) lines at the given indent depth."""
        inline = f"{INDENT * depth}{field_str},"
        if len(inline) <= LINE_LIMIT:
            return [inline]
        # Field itself needs wrapping (very long description)
        if prop.description:
            return [
                f"{INDENT * depth}Field(",
                f'{INDENT * (depth + 1)}description="{description}"',
                f"{INDENT * depth}),",
            ]
        return [f"{INDENT * depth}Field(),"]

    if prop.default_value:
        # Annotated[Optional[T], Field(...)] = default_value
        lines.append(f"{INDENT}{prop.name}: Annotated[")
        lines.append(f"{INDENT * 2}Optional[{base_type}],")
        lines += _field_lines(2)
        lines.append(f"{INDENT}]")
        if default_str is not None:
            lines[-1] += f" = {default_str}"
    elif not prop.required:
        # Optional[Annotated[T, Field(...)]]
        # Keep inner Annotated[...] on one line if it fits
        inner = f"Annotated[{base_type}, {field_str}]"
        inner_line = f"{INDENT * 2}{inner}"
        if len(inner_line) <= LINE_LIMIT:
            lines.append(f"{INDENT}{prop.name}: Optional[")
            lines.append(inner_line)
            lines.append(f"{INDENT}]")
        else:
            lines.append(f"{INDENT}{prop.name}: Optional[")
            lines.append(f"{INDENT * 2}Annotated[")
            lines.append(f"{INDENT * 3}{base_type},")
            lines += _field_lines(3)
            lines.append(f"{INDENT * 2}]")
            lines.append(f"{INDENT}]")
        if default_str is not None:
            lines[-1] += f" = {default_str}"
    else:
        # Annotated[T, Field(...)]
        lines.append(f"{INDENT}{prop.name}: Annotated[")
        lines.append(f"{INDENT * 2}{base_type},")
        lines += _field_lines(2)
        lines.append(f"{INDENT}]")

    return lines


if __name__ == "__main__":
    """
    Convert a TTL file to Python code.

    Command: uv run python libs/naas-abi-core/naas_abi_core/utils/onto2py/onto2py.py
    """
    import argparse

    # Default TTL file
    default_ttl_file = "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/ontologies/modules/ActOfConnectionsOnLinkedIn.ttl"

    parser = argparse.ArgumentParser(description="Send a message via Twilio")
    parser.add_argument(
        "ttl_file",
        nargs="?",
        default=default_ttl_file,
        help="Path to the TTL file to convert to Python code",
    )
    args = parser.parse_args()
    ttl_file = args.ttl_file

    python_code = onto2py(ttl_file)

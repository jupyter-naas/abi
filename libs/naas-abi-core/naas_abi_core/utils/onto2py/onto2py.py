import io
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import rdflib
from rdflib import BNode
from rdflib.collection import Collection


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


def onto2py(ttl_file: str | io.TextIOBase) -> str:
    """
    Convert TTL file to Python classes

    Args:
        ttl_file: Path to TTL file or file-like object

    Returns:
        Generated Python code as string
    """
    if isinstance(ttl_file, str):
        with open(ttl_file, "r") as f:
            content = f.read()
        g = rdflib.Graph()
        g.parse(data=content, format="turtle")
    else:
        content = ttl_file.read()
        g = rdflib.Graph()
        g.parse(data=content, format="turtle")

    # Define common RDF/OWL/SHACL namespaces
    RDF = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
    SHACL = rdflib.Namespace("http://www.w3.org/ns/shacl#")

    # Extract classes and their information
    classes: Dict[str, ClassInfo] = {}

    # Find all OWL classes
    for cls in g.subjects(RDF.type, OWL.Class):
        # Skip blank nodes
        if isinstance(cls, BNode):
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

    # Find all RDFS classes (if not already OWL classes)
    for cls in g.subjects(RDF.type, RDFS.Class):
        # Skip blank nodes
        if isinstance(cls, BNode):
            continue
        if str(cls) not in classes:
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

    # Extract inheritance relationships and OWL restrictions
    for cls_uri, class_info in classes.items():
        for parent in g.objects(rdflib.URIRef(cls_uri), RDFS.subClassOf):
            if str(parent) in classes:
                parent_name = classes[str(parent)].name
                class_info.parent_classes.append(parent_name)
            elif isinstance(parent, BNode):
                # Check if it's an OWL restriction
                restriction_types = list(g.objects(parent, RDF.type))
                if OWL.Restriction in restriction_types:
                    # Extract property from restriction
                    extract_restriction_properties(
                        g, parent, cls_uri, class_info, classes, OWL
                    )

    # Extract properties
    properties: Dict[str, PropertyInfo] = {}

    # Object properties
    for prop in g.subjects(RDF.type, OWL.ObjectProperty):
        prop_name = extract_property_name(prop, g)
        if prop_name:
            properties[str(prop)] = PropertyInfo(
                name=prop_name,
                property_type="object",
                range_classes=get_property_range(g, prop, classes),
                description=get_property_description(g, prop),
            )

    # Data properties
    for prop in g.subjects(RDF.type, OWL.DatatypeProperty):
        prop_name = extract_property_name(prop, g)
        if prop_name:
            properties[str(prop)] = PropertyInfo(
                name=prop_name,
                property_type="data",
                datatype=get_datatype_range(g, prop),
                description=get_property_description(g, prop),
            )

    # Extract SHACL shapes and constraints
    extract_shacl_constraints(g, classes, properties, SHACL)

    # Associate properties with classes based on domain
    for prop_uri, prop_info in properties.items():
        for domain in g.objects(rdflib.URIRef(prop_uri), RDFS.domain):
            if str(domain) in classes:
                class_info = classes[str(domain)]
                # Avoid emitting duplicate property declarations when a property
                # specifies the same domain multiple times in the ontology.
                existing_props = {prop.name: prop for prop in class_info.properties}

                if prop_info.name in existing_props:
                    existing_prop = existing_props[prop_info.name]
                    # Merge stronger constraints if the duplicate carries them.
                    # Only mark as required if BOTH are required (conservative approach)
                    # This prevents properties from being incorrectly marked as required
                    if prop_info.required and existing_prop.required:
                        existing_prop.required = True
                    else:
                        # If either is not required, keep it optional (safer default)
                        existing_prop.required = False
                    # Merge range classes
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

    # Inherit properties from parent classes
    inherit_parent_properties(classes)

    # Add required metadata properties (rdfs:label, dcterms:created, dcterms:creator) to all classes
    add_metadata_properties(g, classes)

    # Generate Python code
    return generate_python_code(classes, properties)


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
    range_classes: Dict[str, Optional[int]] = {}

    for range_cls in g.objects(prop, RDFS.range):
        cls_name: Optional[str] = None
        if str(range_cls) in classes:
            cls_name = classes[str(range_cls)].name
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
                required=True,  # Mandatory property
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
                required=True,  # Mandatory property with default
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
                default_value="os.environ.get('USER')",
                required=True,  # Mandatory property with default
            )
            class_info.properties.append(creator_prop)
            class_info.property_uris[creator_prop_name] = creator_prop_uri


def apply_linting(code: str) -> str:
    """Apply ruff formatting to the generated code"""
    try:
        # Write code to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_file:
            tmp_file.write(code)
            tmp_path = tmp_file.name

        try:
            # Run ruff format
            subprocess.run(
                ["ruff", "format", tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,  # Don't raise on error
            )

            # Run ruff check --fix
            subprocess.run(
                ["ruff", "check", "--fix", tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,  # Don't raise on error
            )

            # Read the formatted code
            with open(tmp_path, "r") as f:
                formatted_code = f.read()

            return formatted_code
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        # If ruff is not available or fails, return original code
        return code
    except Exception:
        # On any other error, return original code
        return code


def generate_python_code(
    classes: Dict[str, ClassInfo], properties: Dict[str, PropertyInfo]
) -> str:
    """Generate Python code from extracted class and property information"""

    # Determine which imports are needed
    needs_list = False
    needs_any = False
    needs_union = False
    needs_datetime = False
    needs_os = False

    # Check all properties to see what types are needed
    for class_info in classes.values():
        for prop in class_info.properties:
            # Check if any range class has cardinality None or > 1 (needs list)
            if prop.property_type == "object":
                for cardinality in prop.range_classes.values():
                    if cardinality is None or cardinality > 1:
                        needs_list = True
                        break
            # Object properties always need Union (for str, URIRef, and classes)
            if prop.property_type == "object":
                needs_union = True
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

    # Build typing imports
    typing_imports = ["Annotated", "Optional", "ClassVar"]
    if needs_list:
        typing_imports.append("List")
    if needs_union:
        typing_imports.append("Union")
    if needs_any:
        typing_imports.append("Any")

    typing_import_str = ", ".join(sorted(typing_imports))

    code_lines = [
        "from __future__ import annotations",
        f"from typing import {typing_import_str}",
        "from pydantic import BaseModel, Field",
        "import uuid",
    ]

    if needs_datetime:
        code_lines.append("import datetime")

    if needs_os:
        code_lines.append("import os")

    code_lines.extend(
        [
            "from rdflib import Graph, URIRef, Literal, Namespace",
            "from rdflib.namespace import RDF, RDFS, OWL, XSD, DCTERMS",
            "",
            "BFO = Namespace('http://purl.obolibrary.org/obo/')",
            "ABI = Namespace('http://ontology.naas.ai/abi/')",
            "CCO = Namespace('https://www.commoncoreontologies.org/')",
            "# Base class for all RDF entities",
            "class RDFEntity(BaseModel):",
            '    """Base class for all RDF entities with URI and namespace management"""',
            '    _namespace: ClassVar[str] = "http://ontology.naas.ai/abi/"',
            '    _uri: str = ""',
            "    _object_properties: ClassVar[set[str]] = set()",
            "    ",
            "    model_config = {",
            "        'arbitrary_types_allowed': True,",
            "        'extra': 'forbid'",
            "    }",
            "    ",
            "    def __init__(self, **kwargs):",
            "        uri = kwargs.pop('_uri', None)",
            "        super().__init__(**kwargs)",
            "        if uri is not None:",
            "            self._uri = uri",
            "        elif not self._uri:",
            '            self._uri = f"{self._namespace}{uuid.uuid4()}"',
            "    ",
            "    @classmethod",
            "    def set_namespace(cls, namespace: str):",
            '        """Set the namespace for generating URIs"""',
            "        cls._namespace = namespace",
            "        ",
            "    def rdf(self, subject_uri: str | None = None) -> Graph:",
            '        """Generate RDF triples for this instance"""',
            "        g = Graph()",
            "        g.bind('cco', CCO)",
            "        g.bind('bfo', BFO)",
            "        g.bind('abi', ABI)",
            "        g.bind('rdfs', RDFS)",
            "        g.bind('rdf', RDF)",
            "        g.bind('owl', OWL)",
            "        g.bind('xsd', XSD)",
            "        ",
            "        # Use stored URI or provided subject_uri",
            "        if subject_uri is None:",
            "            subject_uri = self._uri",
            "        subject = URIRef(subject_uri)",
            "        ",
            "        # Add class type",
            "        if hasattr(self, '_class_uri'):",
            "            g.add((subject, RDF.type, URIRef(self._class_uri)))",
            "        ",
            "        # Add owl:NamedIndividual type",
            "        g.add((subject, RDF.type, OWL.NamedIndividual))",
            "        ",
            "        object_props: set[str] = getattr(self, '_object_properties', set())",
            "        ",
            "        # Add properties",
            "        if hasattr(self, '_property_uris'):",
            "            for prop_name, prop_uri in self._property_uris.items():",
            "                is_object_prop = prop_name in object_props",
            "                prop_value = getattr(self, prop_name, None)",
            "                if prop_value is not None:",
            "                    if isinstance(prop_value, list):",
            "                        for item in prop_value:",
            "                            if hasattr(item, 'rdf'):",
            "                                # Add triples from related object",
            "                                g += item.rdf()",
            "                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))",
            "                            elif is_object_prop and isinstance(item, (str, URIRef)):",
            "                                g.add((subject, URIRef(prop_uri), URIRef(str(item))))",
            "                            else:",
            "                                g.add((subject, URIRef(prop_uri), Literal(item)))",
            "                    elif hasattr(prop_value, 'rdf'):",
            "                        # Add triples from related object",
            "                        g += prop_value.rdf()",
            "                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))",
            "                    elif is_object_prop and isinstance(prop_value, (str, URIRef)):",
            "                        g.add((subject, URIRef(prop_uri), URIRef(str(prop_value))))",
            "                    else:",
            "                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))",
            "        ",
            "        return g",
            "",
            "",
        ]
    )

    # Sort classes to handle inheritance properly
    sorted_classes = topological_sort_classes(classes)

    for class_info in sorted_classes:
        code_lines.extend(generate_class_code(class_info, needs_any))
        code_lines.append("")

    # Add model_rebuild() calls for forward references
    code_lines.append("# Rebuild models to resolve forward references")
    for class_info in sorted_classes:
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
    lines.append(f"    _class_uri: ClassVar[str] = '{class_info.uri}'")

    # Add _name property with rdfs:label
    class_label = class_info.label if class_info.label else class_info.name
    # Escape single quotes in the label
    class_label_escaped = class_label.replace("'", "\\'")
    lines.append(f"    _name: ClassVar[str] = '{class_label_escaped}'")

    # Add property URI mapping
    if class_info.property_uris:
        prop_uris_dict = ", ".join(
            [
                f"'{prop_name}': '{prop_uri}'"
                for prop_name, prop_uri in sorted(class_info.property_uris.items())
            ]
        )
        lines.append(f"    _property_uris: ClassVar[dict] = {{{prop_uris_dict}}}")
    else:
        lines.append("    _property_uris: ClassVar[dict] = {}")

    object_prop_names = sorted(
        {prop.name for prop in properties_list if prop.property_type == "object"}
    )
    if object_prop_names:
        names = ", ".join(f"'{name}'" for name in object_prop_names)
        lines.append(f"    _object_properties: ClassVar[set[str]] = {{{names}}}")
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
            lines.append(f"    {generate_property_code(prop, has_any_import)}")
        emitted_property_group = True

    if not emitted_property_group:
        lines.append("    pass")

    return lines


def generate_property_code(prop: PropertyInfo, has_any_import: bool = False) -> str:
    """Generate code for a single property using Annotated"""

    # Determine base type annotation (without Optional or Annotated)
    if prop.property_type == "object":
        # Build union type parts based on range_classes with their cardinalities
        union_type_parts_set = {"str", "URIRef"}
        union_type_parts_list_set = (
            set()
        )  # Only add list types if cardinality requires it

        # Add classes from range_classes dict, avoiding duplicates
        needs_lists = False
        for class_name, cardinality in prop.range_classes.items():
            if cardinality is None or cardinality > 1:
                needs_lists = True
                union_type_parts_list_set.add(f"List[{class_name}]")
            else:
                union_type_parts_set.add(class_name)

        # Only add List[str] and List[URIRef] if we actually need lists
        if needs_lists:
            union_type_parts_list_set.add("List[str]")
            union_type_parts_list_set.add("List[URIRef]")

        # Merge and preserve a consistent order: scalars first, then lists and custom lists
        union_type_parts = list(sorted(union_type_parts_set))
        union_type_parts_list = sorted(union_type_parts_list_set)
        union_type_parts.extend(union_type_parts_list)

        # Remove duplicates while preserving order
        seen = set()
        filtered_union_type_parts = []
        for part in union_type_parts:
            if part not in seen:
                filtered_union_type_parts.append(part)
                seen.add(part)

        union_types = ", ".join(filtered_union_type_parts)
        base_type = f"Union[{union_types}]"
    elif prop.property_type == "data" and prop.datatype:
        # For data properties, check if any range class has cardinality > 1
        # (data properties don't use range_classes, so this is a fallback)
        base_type = prop.datatype
    else:
        # Use Any if imported, otherwise use object as fallback
        base_type = "Any" if has_any_import else "object"

    # Build Field annotation with description if available
    field_args = []
    if prop.description:
        # Escape quotes in description
        description = prop.description.replace('"', '\\"')
        field_args.append(f'description="{description}"')

    # Build the Field() call
    if field_args:
        field_str = f"Field({', '.join(field_args)})"
    else:
        field_str = "Field()"

    # Determine if we need Optional wrapper
    # For fields with default values, use Annotated[Optional[Type], Field(...)]
    # For required fields without defaults, use Annotated[Type, Field(...)]
    # For optional fields without defaults, use Optional[Annotated[Type, Field(...)]]
    if prop.default_value:
        # Pattern: Annotated[Optional[Type], Field(...)] when there's a default
        final_type = f"Annotated[Optional[{base_type}], {field_str}]"
    elif not prop.required:
        # Pattern: Optional[Annotated[Type, Field(...)]] for optional fields
        annotated_type = f"Annotated[{base_type}, {field_str}]"
        final_type = f"Optional[{annotated_type}]"
    else:
        # Pattern: Annotated[Type, Field(...)] for required fields
        final_type = f"Annotated[{base_type}, {field_str}]"

    # Handle default value assignment
    if prop.default_value:
        # Default value goes after the type annotation
        return f"{prop.name}: {final_type} = {prop.default_value}"
    elif not prop.required:
        return f"{prop.name}: {final_type} = None"
    return f"{prop.name}: {final_type}"


if __name__ == "__main__":
    """
    Convert a TTL file to Python code.

    Command: uv run python libs/naas-abi-core/naas_abi_core/utils/onto2py/onto2py.py
    """
    import argparse
    import os

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
    py_file = os.path.splitext(ttl_file)[0] + ".py"
    with open(py_file, "w") as f:
        f.write(python_code)

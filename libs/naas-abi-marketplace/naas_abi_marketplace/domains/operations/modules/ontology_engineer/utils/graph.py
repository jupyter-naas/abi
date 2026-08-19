from pathlib import Path
from typing import List, Optional, Set, Tuple

from naas_abi_core import logger
from rdflib import OWL, RDF, RDFS, BNode, Graph, URIRef
from rdflib.collection import Collection

URI_TO_GROUP = {
    # BFO core classes (expand as needed)
    "http://purl.obolibrary.org/obo/BFO_0000015": "WHAT",  # Process
    "http://purl.obolibrary.org/obo/BFO_0000035": "WHAT",  # Process Boundary
    "http://purl.obolibrary.org/obo/BFO_0000008": "WHEN",  # Temporal Region
    "http://purl.obolibrary.org/obo/BFO_0000040": "WHO",  # Material Entity
    "http://purl.obolibrary.org/obo/BFO_0000029": "WHERE",  # Site
    "http://purl.obolibrary.org/obo/BFO_0000031": "HOW WE KNOW",  # Generically Dependent Continuant
    "http://purl.obolibrary.org/obo/BFO_0000019": "HOW IT IS",  # Quality
    "http://purl.obolibrary.org/obo/BFO_0000017": "WHY",  # Realizable Entity
    "http://purl.obolibrary.org/obo/BFO_0000016": "WHY",  # Disposition
    "http://purl.obolibrary.org/obo/BFO_0000023": "WHY",  # Role
}


def get_imported_graph(graph: Graph) -> Graph:
    # Load imported ontologies separately to get property labels only (not merged into graph)
    logger.info("Loading imported ontologies for property labels only...")
    imports = list(graph.objects(None, OWL.imports))
    imported_graph = Graph()  # Separate graph for imports
    imported_count = 0
    for import_uri in imports:
        if isinstance(import_uri, URIRef):
            import_url = str(import_uri)
            logger.info(f"  Attempting to load: {import_url}")
            loaded = False
            # Try different formats and methods
            formats_to_try = ["xml", "turtle", "rdf", "owl"]
            for fmt in formats_to_try:
                try:
                    imported_graph.parse(import_url, format=fmt)
                    logger.info(f"  ✓ Successfully loaded as {fmt} (for labels only)")
                    imported_count += 1
                    loaded = True
                    break
                except Exception:
                    continue

            if not loaded:
                logger.warning(
                    f"  ⚠ Could not load {import_uri} (may not be accessible online)"
                )
                logger.warning(
                    "     Property labels will use short names if not found in main file"
                )

    if imported_count > 0:
        logger.info(
            f"  Loaded {imported_count} imported ontology/ontologies (for labels only)"
        )
    else:
        logger.info(
            "  No imported ontologies were loaded (using labels from main file only)"
        )
        # imported_graph = None  # Set to None if no imports loaded
    return imported_graph


def get_short_name(uri: URIRef) -> str:
    """Extract short name from URI."""
    uri_str = str(uri)
    if "#" in uri_str:
        return uri_str.split("#")[-1]
    elif "/" in uri_str:
        return uri_str.split("/")[-1]
    else:
        return uri_str


def get_rdfs_label(
    uri: URIRef, graph: Graph, imported_graph: Optional[Graph] = None
) -> str:
    """
    Get rdfs:label for a URI from main graph and handle imported graph if present.
    Tries to return the label from the main graph first, then from any imported ontology.
    Falls back to short name if no label found.
    """
    # First try main graph
    labels = list(graph.objects(uri, RDFS.label))

    # If not found and imported_graph exists, try imported graph
    if not labels and imported_graph is not None:
        labels = list(imported_graph.objects(uri, RDFS.label))

    # If still not found, try merged graph
    if not labels:
        full_graph: Graph = graph
        if imported_graph is not None:
            full_graph = graph + imported_graph
        labels = list(full_graph.objects(uri, RDFS.label))

    if labels:
        label = str(labels[0])
        # Remove language tag if present
        if "@" in label:
            label = label.split("@")[0]
        return label
    return get_short_name(uri)


def extract_classes_from_union(graph: Graph, union_node: BNode) -> Set[URIRef]:
    """Extract class URIs from an owl:unionOf construct."""
    classes = set()
    try:
        # Use rdflib Collection to handle RDF lists
        collection = Collection(graph, union_node)
        for item in collection:
            if isinstance(item, URIRef):
                classes.add(item)
            elif isinstance(item, BNode):
                # Recursively handle nested structures
                nested_union = list(graph.objects(item, OWL.unionOf))
                if nested_union and isinstance(nested_union[0], BNode):
                    classes.update(extract_classes_from_union(graph, nested_union[0]))
    except Exception:
        # Fallback: manual list traversal
        current = union_node
        while current and current != RDF.nil:
            first = list(graph.objects(current, RDF.first))
            rest = list(graph.objects(current, RDF.rest))

            if first:
                first_item = first[0]
                if isinstance(first_item, URIRef):
                    classes.add(first_item)
                elif isinstance(first_item, BNode):
                    nested_union = list(graph.objects(first_item, OWL.unionOf))
                    if nested_union and isinstance(nested_union[0], BNode):
                        classes.update(
                            extract_classes_from_union(graph, nested_union[0])
                        )

            if rest and rest[0] != RDF.nil and isinstance(rest[0], BNode):
                current = rest[0]
            else:
                break
    return classes


def extract_restriction_targets(graph: Graph, restriction: BNode) -> Set[URIRef]:
    """Extract target classes from an owl:Restriction."""
    targets = set()

    # Check for owl:allValuesFrom
    all_values = list(graph.objects(restriction, OWL.allValuesFrom))
    for value in all_values:
        if isinstance(value, URIRef):
            targets.add(value)
        elif isinstance(value, BNode):
            # Check if it's a union - owl:unionOf points to the list head
            union_of = list(graph.objects(value, OWL.unionOf))
            if union_of and isinstance(union_of[0], BNode):
                # union_of[0] is the list head BNode
                targets.update(extract_classes_from_union(graph, union_of[0]))
            else:
                # Check if the BNode itself is a list head (has RDF.first)
                first = list(graph.objects(value, RDF.first))
                if first:
                    # It's a list head, extract from it
                    targets.update(extract_classes_from_union(graph, value))
                # Note: BNode class expressions are not added to targets
                # since targets is Set[URIRef] and only named classes are tracked

    # Check for owl:someValuesFrom
    some_values = list(graph.objects(restriction, OWL.someValuesFrom))
    for value in some_values:
        if isinstance(value, URIRef):
            targets.add(value)
        elif isinstance(value, BNode):
            union_of = list(graph.objects(value, OWL.unionOf))
            if union_of and isinstance(union_of[0], BNode):
                targets.update(extract_classes_from_union(graph, union_of[0]))
            else:
                # Check if the BNode itself is a list head
                first = list(graph.objects(value, RDF.first))
                if first:
                    targets.update(extract_classes_from_union(graph, value))

    return targets


def extract_relationships(graph: Graph, class_uri: URIRef) -> List:
    """
    Extract relationships from a class through its rdfs:subClassOf restrictions.

    Returns list of (source_class, target_class, property_label) tuples.
    """
    relationships = []

    # Get all subClassOf statements
    subclasses = list(graph.objects(class_uri, RDFS.subClassOf))
    for subclass in subclasses:
        # if isinstance(subclass, URIRef):
        #     # Direct subclass relationship
        #     relationships.append((class_uri, subclass, "subClassOf"))
        if isinstance(subclass, BNode):
            # Check if it's a restriction
            types = list(graph.objects(subclass, RDF.type))
            if OWL.Restriction in types:
                # Get the property
                properties = list(graph.objects(subclass, OWL.onProperty))
                if properties:
                    property_uri = properties[0]
                    targets = extract_restriction_targets(graph, subclass)
                    for target in targets:
                        relationships.append((class_uri, target, property_uri))

    return relationships


def get_class_id_prefix(uri: URIRef, graph: Graph) -> str:
    """Get the prefix for a class URI (e.g., 'bfo' for BFO URIs)."""
    uri_str = str(uri)
    # Check namespaces in the graph
    for prefix, namespace in graph.namespaces():
        if uri_str.startswith(str(namespace)):
            return str(prefix)
    # Fallback: extract from URI
    if "bfo" in uri_str.lower() or "BFO" in uri_str:
        return "bfo"
    elif "abi" in uri_str.lower():
        return "abi"
    return "class"


def get_inverse_property(property_uri: URIRef, graph: Graph) -> Optional[URIRef]:
    """
    Get the inverse property of a given property URI.
    Checks both owl:inverseOf directions.
    """
    # Check if this property has an inverse defined
    inverses = list(graph.objects(property_uri, OWL.inverseOf))
    if inverses and isinstance(inverses[0], URIRef):
        return inverses[0]

    # Check if any property has this property as its inverse
    for prop in graph.subjects(OWL.inverseOf, property_uri):
        if isinstance(prop, URIRef):
            return prop

    return None


def get_group_from_class_hierarchy(
    class_uri: URIRef, graph: Graph, visited: Optional[Set[URIRef]] = None
) -> Optional[str]:
    """
    Traverse up the subclass hierarchy to find a group from URI_TO_GROUP.
    Returns the first matching group found, or None if none found.
    """
    if visited is None:
        visited = set()

    # Avoid infinite loops
    if class_uri in visited:
        return None
    visited.add(class_uri)

    # Check if this class URI is in URI_TO_GROUP
    class_uri_str = str(class_uri)
    if class_uri_str in URI_TO_GROUP:
        return URI_TO_GROUP[class_uri_str]

    # Traverse up the subclass hierarchy
    subclasses = list(graph.objects(class_uri, RDFS.subClassOf))
    for subclass in subclasses:
        if isinstance(subclass, URIRef):
            # Recursively check parent classes
            group = get_group_from_class_hierarchy(subclass, graph, visited)
            if group:
                return group

    return None


def parse_turtle_ontology(
    turtle_path: str,
    imported_ontologies: Optional[List[str]] = None,
) -> Tuple[Graph, Graph, Set[URIRef], Set[Tuple[URIRef, URIRef, URIRef]]]:
    """
    Parse a Turtle ontology file and extract classes and relationships.

    Args:
        turtle_path: Path to the Turtle (.ttl) file
        imported_ontologies: Optional list of additional ontology paths/URLs to import

    Returns:
        Tuple of (main_graph, imported_graph, classes, unique_relationships, ttl_content)
        - main_graph: The parsed main Turtle file graph
        - imported_graph: Graph containing imported ontologies (for labels)
        - classes: Set of class URIs found in the ontology
        - unique_relationships: Set of unique (source, target, property_uri) tuples
        - ttl_content: Raw content of the TTL file (for comment extraction)
    """
    turtle_path_obj = Path(turtle_path)
    if not turtle_path_obj.exists():
        raise FileNotFoundError(f"Turtle file not found: {turtle_path}")

    # Parse the Turtle file
    logger.info(f"Parsing Turtle file: {turtle_path}")
    graph = Graph()
    graph.parse(str(turtle_path_obj), format="turtle")

    # Get imported graph
    imported_graph = get_imported_graph(graph)

    # Add additional imported ontologies if provided
    if imported_ontologies and len(imported_ontologies) > 0:
        for imported_ontology in imported_ontologies:
            try:
                logger.info(f"Loading additional ontology: {imported_ontology}")
                imported_graph.parse(imported_ontology, format="turtle")
            except Exception as e:
                logger.warning(f"  Warning: Could not load {imported_ontology}: {e}")

    # Find all owl:Class instances
    logger.info("Extracting owl:Class entities...")
    classes = set()
    for class_uri in graph.subjects(RDF.type, OWL.Class):
        if isinstance(class_uri, URIRef):
            classes.add(class_uri)

    logger.info(f"Found {len(classes)} explicitly declared classes")

    # Collect classes referenced in restrictions (owl:someValuesFrom, owl:allValuesFrom)
    logger.info("Collecting classes referenced in restrictions...")
    classes_from_restrictions = set()

    # Check all restrictions in the graph to find referenced classes
    for restriction in graph.subjects(RDF.type, OWL.Restriction):
        if isinstance(restriction, BNode):
            targets = extract_restriction_targets(graph, restriction)
            for target in targets:
                if isinstance(target, URIRef):
                    classes_from_restrictions.add(target)

    # Add classes found in restrictions to the classes set
    classes.update(classes_from_restrictions)
    if classes_from_restrictions:
        logger.info(
            f"Found {len(classes_from_restrictions)} additional classes referenced in restrictions"
        )

    logger.info(f"Total classes: {len(classes)}")

    # Extract relationships and deduplicate (now with complete classes set, and remove inverse duplicates)
    logger.info(
        "Extracting relationships from restrictions and deduplicating, removing inverse duplicates..."
    )
    unique_relationships = set()
    seen_relations = set()

    for class_uri in classes:
        relationships = extract_relationships(graph, class_uri)
        for source, target, property_uri in relationships:
            if source in classes and target in classes:
                # Consider (source, target, property_uri) and (target, source, property_uri) as inverses
                key = (source, target)
                inverse_key = (target, source)
                if key not in seen_relations and inverse_key not in seen_relations:
                    unique_relationships.add((source, target, property_uri))
                    seen_relations.add(key)

    logger.info(
        f"Found {len(unique_relationships)} unique relationships (with inverses deduplicated)"
    )

    return graph, imported_graph, classes, unique_relationships

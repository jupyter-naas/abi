from rdflib import Graph, URIRef, RDF, OWL, RDFS
from pprint import pprint
import pydash

# Ontology operators mapping
ONTOLOGY_OPERATORS = {"unionOf": "or", "intersectionOf": "and", "complementOf": "not"}

class OntologyPropertyExtractor:
    def __init__(self, file_path):
        self.graph = Graph()
        self.graph.parse(file_path, format="turtle")
        self.operators = ONTOLOGY_OPERATORS
        self._ = pydash
        
        # Initialize data structures like in generate_docs
        self.onto_tuples = {}
        self.onto_classes = {}
        self.onto = {}
        
        # Create basic mapping for common properties
        self.mapping = {
            "http://www.w3.org/2000/01/rdf-schema#label": "label",
            "http://www.w3.org/2000/01/rdf-schema#domain": "domain",
            "http://www.w3.org/2000/01/rdf-schema#range": "range",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "type",
            "http://www.w3.org/2000/01/rdf-schema#subClassOf": "subclassOf",
            "http://www.w3.org/2002/07/owl#unionOf": "unionOf",
            "http://www.w3.org/2002/07/owl#intersectionOf": "intersectionOf",
            "http://www.w3.org/2002/07/owl#complementOf": "complementOf",
        }
        
        # Load triples into onto_tuples structure
        self._load_triples()
        
        # Load classes
        self._load_classes()
        
    def _load_triples(self):
        """Load SPO triples into onto_tuples dictionary structure."""
        for s, p, o in self.graph:
            self._handle_onto_tuples(s, p, o)
            
            # Keep only the predicates that are in the mapping.
            if str(p) not in self.mapping:
                continue

            # If the subject is not in the onto dictionary, we create a new dict for it.
            if str(s) not in self.onto:
                self.onto[str(s)] = {"__id": str(s)}

            # If the predicate is not in the onto dict, we create a new list for it.
            if self.mapping[str(p)] not in self.onto[str(s)]:
                self.onto[str(s)][self.mapping[str(p)]] = []

            # We append the object to the list of the predicate.
            self.onto[str(s)][self.mapping[str(p)]].append(str(o))
    
    def _handle_onto_tuples(self, s, p, o):
        """Load SPO in onto_tuples dictionary."""
        if str(s) not in self.onto_tuples:
            self.onto_tuples[str(s)] = []
        self.onto_tuples[str(s)].append((p, o))
    
    def _load_classes(self):
        """Load classes from the ontology."""
        # Filter the classes from the ontology.
        _onto_classes = self._.filter_(
            self.onto,
            lambda x: "http://www.w3.org/2002/07/owl#Class" in x["type"]
            if "type" in x
            else None,
        )
        
        # Remove subclassOf that are restrictions to keep it simple for now.
        for cls in _onto_classes:
            cls["subclassOf"] = self._.filter_(
                cls.get("subclassOf", []), lambda x: True if "http" in x else False
            )

        # Rebuild dictionary with __id as the key
        self.onto_classes = {e["__id"]: e for e in _onto_classes}
    
    def _get_first_rest(self, tpl):
        """Get the values from unionOf, intersectionOf and complementOf."""
        first = None
        rest = None
        for i in tpl:
            a, b = i

            if str(a) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#first":
                first = str(b)

            if (
                str(a) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"
                and str(b) != "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"
            ):
                rest = str(b)
        return first, rest

    def get_linked_classes(self, cls_id, rel_type=None):
        """Recursive function to build a tree of classes based on unionOf, intersectionOf and complementOf."""
        # If it's a leaf we return a dict with the class id and the operator.
        if "http" in cls_id:
            if rel_type is not None and rel_type in self.operators:
                return {self.operators[rel_type]: [cls_id]}
            return [cls_id]

        # If it's a class, we want to go over the unionOf, intersectionOf and complementOf.
        if cls_id in self.onto_classes:
            cls = self.onto_classes[cls_id]
            res = (
                [
                    self.get_linked_classes(e, "unionOf")
                    for e in self._.get(cls, "unionOf", [])
                ]
                + [
                    self.get_linked_classes(e, "intersectionOf")
                    for e in self._.get(cls, "intersectionOf", [])
                ]
                + [
                    self.get_linked_classes(e, "complementOf")
                    for e in self._.get(cls, "complementOf", [])
                ]
            )
            return res
        else:
            # If it's not a class, then we will have a 'first' and a 'rest' to handle.
            first, rest = self._get_first_rest(self.onto_tuples[cls_id])

            # We grab the operator based on the rel_type.
            operator = self.operators[rel_type]

            # We get the left/first value.
            left = self.get_linked_classes(first, rel_type)
            if rest:
                # We get the right/rest value.
                right = self.get_linked_classes(rest, rel_type)

                if operator in right and operator in left:
                    if (
                        operator in right
                        and type(right[operator]) is dict
                        and operator in right[operator]
                        and type(right[operator][operator]) is list
                    ):
                        right[operator] = right[operator][operator]

                    return {operator: self._.flatten([left[operator], right[operator]])}
                else:
                    return {operator: self._.flatten([left, right])}
            else:
                return {operator: left}

    def map_ranges_domains(self, property_data):
        """Map the ranges and domains to the classes by calling get_linked_classes."""
        if "domain" in property_data:
            property_data["domain"] = self._.map_(
                property_data["domain"],
                lambda x: x if "http" in x else self.get_linked_classes(x)[0],
            )
        if "range" in property_data:
            property_data["range"] = self._.map_(
                property_data["range"],
                lambda x: x if "http" in x else self.get_linked_classes(x)[0],
            )
        return property_data

    def get_object_properties_from_class(self, class_uri):
        """Get all object properties for a given class using sophisticated logic."""
        object_properties = []
        
        # Query for object properties with domain class_uri or union containing it
        for s, p, o in self.graph.triples((None, RDF.type, OWL.ObjectProperty)):
            property_data = {
                "object_property_uri": str(s),
                "object_property_label": str(self.graph.value(s, RDFS.label) or ""),
                "domain": [],
                "range": []
            }
            
            # Collect all domains
            for domain_uri in self.graph.objects(s, RDFS.domain):
                property_data["domain"].append(str(domain_uri))
            
            # Collect all ranges
            for range_uri in self.graph.objects(s, RDFS.range):
                property_data["range"].append(str(range_uri))
            
            # Apply sophisticated mapping logic from generate_docs
            property_data = self.map_ranges_domains(property_data)
            
            # Check if class_uri is in the domain
            if self._class_matches_domain(str(class_uri), property_data["domain"]):
                # Process ranges with sophisticated logic
                processed_ranges = self._process_ranges(property_data["range"])
                
                object_properties.append({
                    "object_property_uri": str(s),
                    "object_property_label": property_data["object_property_label"],
                    "ranges": processed_ranges
                })
        
        return object_properties
    
    def _class_matches_domain(self, class_uri, domains):
        """Check if class_uri matches any of the domains (including complex expressions)."""
        for domain in domains:
            if isinstance(domain, str) and domain == class_uri:
                return True
            elif isinstance(domain, dict):
                # Handle complex expressions
                if "or" in domain and class_uri in domain["or"]:
                    return True
                if "and" in domain and class_uri in domain["and"]:
                    return True
        return False
    
    def _process_ranges(self, ranges):
        """Process ranges with sophisticated logic to handle complex expressions."""
        processed_ranges = []
        
        def _get_labeled_uri(uri):
            """Get label for a URI."""
            range_uri = URIRef(uri)
            range_label = self.graph.value(range_uri, RDFS.label)
            return {
                "uri": uri,
                "label": str(range_label) if range_label else None
            }

        def _process_range_item(range_item):
            """Process range item recursively."""
            if isinstance(range_item, str):
                return _get_labeled_uri(range_item)
            elif isinstance(range_item, dict):
                processed_dict = {}
                for key, value in range_item.items():
                    if key in ["or", "and", "not"]:
                        if isinstance(value, list):
                            processed_dict[key] = [_process_range_item(item) for item in value]
                        else:
                            processed_dict[key] = _process_range_item(value)
                return processed_dict
            return range_item

        for range_item in ranges:
            processed_range = _process_range_item(range_item)
            processed_ranges.append(processed_range)
        
        return processed_ranges


# Main execution
file_path = "src/core/modules/ontology/ontologies/top-level/bfo-core.ttl"
class_uri = URIRef("http://purl.obolibrary.org/obo/BFO_0000040")

# Initialize the extractor
extractor = OntologyPropertyExtractor(file_path)

# Get all object properties for the specified class
object_properties = extractor.get_object_properties_from_class(class_uri)

pprint(object_properties)
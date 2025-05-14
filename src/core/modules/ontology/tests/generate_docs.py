import copy
import pydash as _
import random
from abi import logger
from src import services
from rdflib import Graph, RDF, OWL, RDFS, URIRef

class OntologyYaml:
    def __init__(self):
        pass
        
    @staticmethod
    def rdf_to_yaml(
        graph,
        class_colors_mapping: dict = {},
        top_level_class: str = 'http://purl.obolibrary.org/obo/BFO_0000001',
        display_relations_names: bool = True,
    ):
        """Translate RDF graph to YAML.

        Args:
            graph (Graph): RDF graph to translate.
            class_colors_mapping (dict): Mapping of classes to colors.
            top_level_class (str): Top level class to compute class levels.
            display_relations_names (bool): Whether to display relations names.
        """
        translator = Translator()
        return translator.translate(
            graph,
            class_colors_mapping=class_colors_mapping,
            top_level_class=top_level_class,
            display_relations_names=display_relations_names
        )


class Translator:
    def __init__(self):
        # Dictionary to store ontology components
        self.onto = {}
        self.onto_tuples = {}
        self.onto_oprop = {}
        self.onto_dprop = {}
        self.onto_classes = {}
        self.amount_per_level = {}
        self.mapping_oprop = {}

        # Init ontology schemas
        consolidated = services.triple_store_service.get_schema_graph()
        schema_graph = Graph()

        # Filter for desired types
        desired_types = {
            OWL.Class,
            OWL.DatatypeProperty,
            OWL.ObjectProperty,
            OWL.AnnotationProperty
        }
        
        # Add all triples where subject is of desired type
        for s, p, o in consolidated.triples((None, RDF.type, None)):
            if o in desired_types:
                # Add the type triple
                schema_graph.add((s, p, o))
                # Add all triples where this subject is involved
                for s2, p2, o2 in consolidated.triples((s, None, None)):
                    schema_graph.add((s2, p2, o2))
                for s2, p2, o2 in consolidated.triples((None, None, s)):
                    schema_graph.add((s2, p2, o2))
        self.ontology_schemas = schema_graph

        # Init mapping
        mapping = {}
        for s, p, o in self.ontology_schemas.triples((None, RDFS.label, None)):
            if isinstance(s, URIRef):
                mapping[str(s)] = str(o)
            
        # Add standard RDF terms
        rdf_terms = {
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "type",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#first": "first", 
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest": "rest",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil": "nil"
        }
        
        # Add RDFS terms
        rdfs_terms = {
            "http://www.w3.org/2000/01/rdf-schema#domain": "domain",
            "http://www.w3.org/2000/01/rdf-schema#label": "label",
            "http://www.w3.org/2000/01/rdf-schema#range": "range",
            "http://www.w3.org/2000/01/rdf-schema#subClassOf": "subclassOf"
        }
        
        # Add OWL terms
        owl_terms = {
            "http://www.w3.org/2002/07/owl#complementOf": "complementOf",
            "http://www.w3.org/2002/07/owl#intersectionOf": "intersectionOf", 
            "http://www.w3.org/2002/07/owl#inverseOf": "inverseOf",
            "http://www.w3.org/2002/07/owl#unionOf": "unionOf"
        }
        
        # Add SKOS terms
        skos_terms = {
            "http://www.w3.org/2004/02/skos/core#altLabel": "altLabel",
            "http://www.w3.org/2004/02/skos/core#definition": "definition",
            "http://www.w3.org/2004/02/skos/core#example": "example"
        }
        
        # Add DC terms
        dc_terms = {
            "http://purl.org/dc/elements/1.1/identifier": "identifier",
            "http://purl.org/dc/terms/title": "title",
            "http://purl.org/dc/terms/description": "description",
            "http://purl.org/dc/terms/license": "license",
            "http://purl.org/dc/terms/rights": "rights",
            "http://purl.org/dc/terms/contributor": "contributor"
        }
        
        # Update mapping with all terms
        mapping.update(rdf_terms)
        mapping.update(rdfs_terms)
        mapping.update(owl_terms)
        mapping.update(skos_terms)
        mapping.update(dc_terms)
        self.mapping = mapping

        # Define logical operators mapping
        self.operators = {
            'unionOf': 'or',
            'intersectionOf': 'and',
            'complementOf': 'not'
        }
    
    def translate(
        self, 
        graph,
        class_colors_mapping,
        top_level_class,
        display_relations_names
    ):
        """Translate RDF graph to YAML.

        Args:
            graph (Graph): RDF graph to translate.
            class_colors_mapping (dict): Mapping of classes to colors.
            top_level_class (str): Top level class to compute class levels.
            display_relations_names (bool): Whether to display relations names.
        """
        # Extract triples from the Graph.
        self.load_triples(graph)
        
        # Load the classes from the ontology.
        self.load_classes()
        
        # Compute class levels for the hierarchy building.
        self.compute_class_levels(top_level_class)
        
        # Got object properties.
        self.load_object_properties()

        # Got data properties.
        self.load_data_properties()
    
        # Get individuals.
        self.load_individuals()

        # Map object properties labels
        self.map_oprop_labels()

        # Save ontology data as JSON
        self.save_json()
        
        # Create the YAML file.
        return self.create_yaml(class_colors_mapping, display_relations_names)

    def __handle_onto_tuples(self, s, p, o):
        """Load SPO in onto_tuples dictionary.

        Args:
            s (_type_): Subject
            p (_type_): Predicate
            o (_type_): Object
        """
        
        if str(s) not in self.onto_tuples:
            self.onto_tuples[str(s)] = []
        
        self.onto_tuples[str(s)].append((p, o))
    
    def load_triples(self, g):
        """Load the triples from the graph into the ontology dictionary.

        Args:
            graph (_type_): _description_
        """
        # Consolidates graph with ConsolidatedOntology.ttl schema
        g += self.ontology_schemas

        # Load the triples from the graph into the ontology dictionary.
        for s, p, o in g:
            self.__handle_onto_tuples(s, p, o)
            
            # Keep only the predicates that are in the mapping.
            if str(p) not in self.mapping:
                # logger.debug(f"🛑 Predicate not in mapping: {str(p)}")
                continue

            # If the subject is not in the onto dictionary, we create a new dict for it.
            # We also add the __id field to the dict with the subject as the value.
            if str(s) not in self.onto:
                self.onto[str(s)] = {
                    '__id': str(s)
                }
            
            # If the predicate is not in the onto dict, we create a new list for it.
            # We create a list because there can be multiple values for the same predicate.
            if self.mapping[str(p)] not in self.onto[str(s)]:
                self.onto[str(s)][self.mapping[str(p)]] = []
            
            # We append the object to the list of the predicate.
            self.onto[str(s)][self.mapping[str(p)]].append(str(o))

    def load_classes(self):
        # We filter the classes from the ontology.
        _onto_classes = _.filter_(self.onto, lambda x: 'http://www.w3.org/2002/07/owl#Class' in x['type'] if 'type' in x else None)

        # We remove the subclassOf that are restrictions to keep it simple for now.
        # TODO: Resolve the restrictions to be able to display/use them later on.
        for cls in _onto_classes:
            cls['subclassOf'] = _.filter_(cls.get('subclassOf', []), lambda x: True if 'http' in x else False)

        # We re build a dictionary with the __id as the key as it is easier to access the data this way.
        self.onto_classes = {e['__id']: e for e in _onto_classes}
    
    def __compute_class_levels(self, cls_id, level=0, level_path="Entity", hierarchy=[{"uri": "http://purl.obolibrary.org/obo/BFO_0000001", "label": "Entity", "level": 0}]):
        if cls_id in self.onto_classes:
            self.onto_classes[cls_id]['level'] = level
            self.onto_classes[cls_id]['level_path'] = level_path
            self.onto_classes[cls_id]['hierarchy'] = hierarchy

            if level not in self.amount_per_level:
                self.amount_per_level[level] = 0

            self.amount_per_level[level] += 1

            subclassOf = _.filter_(self.onto_classes, lambda x: cls_id in x['subclassOf'])
            for subclass in subclassOf:
                self.__compute_class_levels(subclass['__id'], level + 1, level_path + "/" + subclass['label'][0].capitalize(), hierarchy + [{"uri": subclass['__id'], "label": subclass['label'][0].capitalize(), "level": level + 1}])
    
    def compute_class_levels(self, cls_id):
        # Reset amount_per_level
        self.amount_per_level = {}
        self.__compute_class_levels(cls_id)

    # get_first_rest is used to get the values from unionOf, intersectionOf and complementOf.
    def __get_first_rest(self, tpl):
        first = None
        rest = None
        for i in tpl:
            a, b = i
            
            if str(a) == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#first':
                first = str(b)
                
            if str(a) == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#rest' and str(b) != 'http://www.w3.org/1999/02/22-rdf-syntax-ns#nil':
                rest = str(b)
        return first, rest  

    # get_linked_classes is a recursive function used for Object Properties ranges and domains.
    # It will build a tree of classes based on the unionOf, intersectionOf and complementOf.
    # It is usefull to understand what are the conditions for a class to be in the range or domain of an object property.
    def get_linked_classes(self, cls_id, rel_type=None):
        # If it's a leaf we return a dict with the class id and the operator.
        if 'http' in cls_id:
            if rel_type is not None and rel_type in self.operators:
                return {self.operators[rel_type]: [cls_id]}
            return [cls_id]
        
        # If it's a class, we want to go over the unionOf, intersectionOf and complementOf.
        if cls_id in self.onto_classes:
            cls = self.onto_classes[cls_id]
            res = \
                [self.get_linked_classes(e, 'unionOf') for e in _.get(cls, 'unionOf', [])] + \
                [self.get_linked_classes(e, 'intersectionOf') for e in _.get(cls, 'intersectionOf', [])] + \
                [self.get_linked_classes(e, 'complementOf') for e in _.get(cls, 'complementOf', [])]
            return res
        else:
            # If it's not a class, then we will have a 'first' and a 'rest' to handle.
            first, rest = self.__get_first_rest(self.onto_tuples[cls_id])
            
            # We grab the operator based on the rel_type.
            operator = self.operators[rel_type]
            
            # We get the left/first value.
            left = self.get_linked_classes(first, rel_type)
            if rest:
                # We get the right/rest value.
                right = self.get_linked_classes(rest, rel_type)

                if operator in right and operator in left:
                    
                    if operator in right and type(right[operator]) is dict and operator in right[operator] and type(right[operator][operator]) is list:
                        right[operator] = right[operator][operator]
                    
                    return {operator: _.flatten([left[operator], right[operator]])}
                else:
                    return {operator: _.flatten([left, right])}
            else:
                return {operator: left}
    
    # We map the ranges and domains to the classes by calling get_linked_classes.
    def map_ranges_domains(self, x):
        if 'range' in x:
            x['range'] = _.map_(x['range'], lambda x: x if 'http' in x else self.get_linked_classes(x)[0])
        if 'domain' in x:
            x['domain'] = _.map_( x['domain'], lambda x: x if 'http' in x else self.get_linked_classes(x)[0])
        return x

    def load_object_properties(self):
        # We filter the object properties from the ontology.
        _onto_oprop = _.filter_(self.onto, lambda x: 'http://www.w3.org/2002/07/owl#ObjectProperty' in x['type'] if 'type' in x else None)
    
        # For each Object property, we map the ranges and domains.
        for i in _onto_oprop:
            self.map_ranges_domains(i)
            
        # We re build a dictionary with the __id as the key as it is easier to access the data this way.
        self.onto_oprop = {e['__id']: e for e in _onto_oprop}

    def load_data_properties(self):
        # We filter the data properties from the ontology.
        _onto_dprop = _.filter_(self.onto, lambda x: 'http://www.w3.org/2002/07/owl#DatatypeProperty' in x['type'] if 'type' in x else None)

        # We re build a dictionary with the __id as the key as it is easier to access the data this way.
        self.onto_dprop = {e['__id']: e for e in _onto_dprop}

    def save_json(self):
        """Save ontology data as JSON.

        Returns:
            dict: Dictionary containing ontology data structures
        """
        import json
        import os

        # Create the docs/ontology/reference/model directory if it doesn't exist
        os.makedirs("docs/ontology/reference/model", exist_ok=True)

        # Save the ontology data as JSON
        with open("docs/ontology/reference/model/ontology.json", "w") as f:
            json.dump(self.onto, f, indent=4, ensure_ascii=False)

        with open("docs/ontology/reference/model/onto_tuples.json", "w") as f:
            json.dump(self.onto_tuples, f, indent=4, ensure_ascii=False)
        
        with open("docs/ontology/reference/model/onto_oprop.json", "w") as f:
            json.dump(self.onto_oprop, f, indent=4, ensure_ascii=False)
        
        with open("docs/ontology/reference/model/onto_dprop.json", "w") as f:
            json.dump(self.onto_dprop, f, indent=4, ensure_ascii=False)
        
        with open("docs/ontology/reference/model/onto_classes.json", "w") as f:
            json.dump(self.onto_classes, f, indent=4, ensure_ascii=False)
        
        with open("docs/ontology/reference/model/amount_per_level.json", "w") as f:
            json.dump(self.amount_per_level, f, indent=4, ensure_ascii=False)

    def load_individuals(self):
        self.onto_individuals = _.filter_(self.onto, lambda x: 'http://www.w3.org/2002/07/owl#NamedIndividual' in x['type'] if 'type' in x else None)

    def map_oprop_labels(self):
        # Map Object properties with label
        self.mapping_oprop = {}
        for o in self.onto_oprop:
            if o and "label" in self.onto_oprop.get(o):
                self.mapping_oprop[o] = self.onto_oprop.get(o).get("label")[0]
        
    def create_yaml(self, class_color, display_relations_names):
        # Init
        all_classes = {}
        classes = {}
        entities = []
        prefixes = {
            'xsd': 'http://www.w3.org/2001/XMLSchema#',
            'abi': 'http://ontology.naas.ai/abi/',
            'bfo': 'http://purl.obolibrary.org/obo/',
            'cco': 'https://www.commoncoreontologies.org/',
        }
        
        # Loop on classes
        import os
        dir_path = os.path.join("docs", "ontology", "reference", "model")
        for onto_class in self.onto_classes:
            if onto_class.startswith("http"):
                onto_class_dict = self.onto_classes.get(onto_class)
                print(onto_class_dict)
                level = onto_class_dict.get("level", 0)
                level_path = onto_class_dict.get("level_path", "")

                # H1 : Title
                label = onto_class_dict.get("label", [""])[0]
                markdown_content = f"# {label.capitalize()}\n\n"

                # H2 : Overview
                markdown_content += f"## Overview\n\n"

                # H3 : Definition
                markdown_content += f"### Definition\n"
                definition = onto_class_dict.get("definition", [])
                if definition:
                    markdown_content += "\n".join(definition) + "\n\n"
                else:
                    markdown_content += "Not defined.\n\n"

                # Examples
                markdown_content += "### Examples\n"
                example = onto_class_dict.get("example", [])
                if example:
                    markdown_content += "\n".join(f"- {ex}" for ex in example) + "\n\n"
                else:
                    markdown_content += "Not defined.\n\n"

                # H3 : Aliases
                markdown_content += "### Aliases\n"
                aliases = onto_class_dict.get("altLabel", [])
                if aliases:
                    markdown_content += "\n".join(f"- {alias}" for alias in aliases) + "\n\n"
                else:
                    markdown_content += "Not defined.\n\n"

                # H3 : URI
                markdown_content += "### URI\n"
                uid = onto_class_dict.get("__id")
                if uid:
                    markdown_content += f"{uid}\n\n"
                else:
                    markdown_content += "Not defined.\n\n"

                # H3 : Subclass Of
                markdown_content += "### Subclass Of\n"
                subclass = onto_class_dict.get("subclassOf", [])
                if subclass:
                    markdown_content += "\n".join(f"- {sub}" for sub in subclass) + "\n\n"
                else:
                    markdown_content += "Not defined.\n\n"

                # H3 : Ontology Reference
                markdown_content += "### Ontology Reference\n"
                ontology_reference = onto_class_dict.get("is curated in ontology", [])
                if ontology_reference:
                    markdown_content += "\n".join(f"- {ref}" for ref in ontology_reference) + "\n\n"
                else:
                    markdown_content += "Not defined.\n\n"

                # H3 : Hierarchy
                markdown_content += "### Hierarchy\n"
                markdown_content += "```mermaid\n"
                markdown_content += "graph BT\n"

                # Split level path and create hierarchy
                hierarchy = onto_class_dict.get("hierarchy", [])
                if hierarchy:
                    nodes = []
                    nodes.append("    BFO_0000001(Entity):::BFO\n")
                    
                    # Create nodes and connections
                    for i, level in enumerate(hierarchy[1:], 1):
                        safe_name = level.get("uri").split("/")[-1]
                        parent_name = hierarchy[i-1].get("uri").split("/")[-1] if i > 1 else "BFO_0000001"
                        formatted_label = level.get("label").replace(' ', '<br>')
                        if "BFO" in parent_name:
                            parent_group = "BFO"
                        elif "onto" in parent_name:
                            parent_group = "CCO"
                        else:
                            parent_group = "ABI"
                            
                        nodes.append(f"    {safe_name}({formatted_label}):::{parent_group}-->{parent_name}\n")
                    
                    # Add nodes to markdown
                    markdown_content += "".join(reversed(nodes))
                    
                    # Add styling
                    markdown_content += "    \n"
                    markdown_content += "    classDef BFO fill:#97c1fb,color:#060606\n"
                    markdown_content += "    classDef CCO fill:#e4c51e,color:#060606\n"
                    markdown_content += "    classDef ABI fill:#48DD82,color:#060606\n"
                
                markdown_content += "```\n\n"

                # H2 : Properties
                markdown_content += "## Properties\n"
                parents = [h['uri'] for h in hierarchy]
                print("Parents : ", parents)

                # H3 : Data Properties
                dproperties = _.filter_(self.onto_dprop.values(), lambda x: 'domain' in x and any(uri in x['domain'] for uri in parents))
                print("Data properties : ", dproperties)
                data_properties = []
                for dprop in sorted(dproperties, key=lambda x: x.get('__id', 0)):
                    d_predicate = dprop.get('__id', '')
                    d_domain = dprop.get("domain")
                    if d_domain:
                        d_domain = str(d_domain)
                    d_range = dprop.get("range")
                    if d_range:
                        d_range = str(d_range)
                    d_label = dprop.get('label', [''])[0]
                    d_definition = dprop.get('definition', [''])[0]
                    d_example = dprop.get('example', [''])[0]
                    data_properties.append({
                        "predicate": d_predicate,
                        "label": d_label,
                        "domain": d_domain,
                        "range": d_range,
                        "definition": d_definition,
                        "example": d_example
                    })
                if len(data_properties) > 0:
                    markdown_content += "### Data Properties\n"
                    markdown_content += "| Label | Definition | Example | Domain | Range |\n"
                    markdown_content += "|-------|------------|---------|--------|-------|\n"
                    from pprint import pprint
                    print("Data properties : ")
                    pprint(data_properties)
                    for dprop in data_properties:
                        markdown_content += f"| [{dprop['label']}]({dprop['predicate']}) | {dprop['domain']} | {dprop['range']} | {dprop['definition']} | {dprop['example']} |\n"
                    markdown_content += "\n"

                # H3 : Object Properties
                oproperties = _.filter_(self.onto_oprop.values(), lambda x: 'domain' in x and any(uri in x['domain'] for uri in parents))
                print("Object properties : ", oproperties)
                object_properties = []
                for oprop in sorted(oproperties, key=lambda x: x.get('__id', 0)):
                    o_predicate = oprop.get('__id', '')
                    o_domain = oprop.get("domain")
                    if o_domain:
                        o_domain = str(o_domain)
                    o_range = oprop.get("range")
                    if o_range:
                        o_range = str(o_range)
                    o_label = oprop.get('label', [''])[0]
                    o_definition = oprop.get('definition', [''])[0]
                    o_example = oprop.get('example', [''])[0]
                    o_inverse_of = oprop.get('inverseOf')
                    if o_inverse_of:
                        o_inverse_of = str(o_inverse_of)
                    data_properties.append({
                        "predicate": o_predicate,
                        "label": o_label,
                        "definition": o_definition,
                        "example": o_example,
                        "domain": o_domain,
                        "range": o_range,
                        "inverseOf": o_inverse_of
                    })
                if len(object_properties) > 0:
                    markdown_content += "### Object Properties\n"
                    markdown_content += "| Label | Definition | Example | Domain | Range | Inverse Of |\n"
                    markdown_content += "|-------|------------|---------|--------|-------|------------|\n"
                    from pprint import pprint
                    print("Object properties : ")
                    pprint(object_properties)
                    for oprop in object_properties:
                        markdown_content += f"| [{oprop['label']}]({oprop['predicate']}) | {oprop['definition']} | {oprop['example']} | {oprop['domain']} | {oprop['range']} | {oprop['inverseOf']} |\n"
                    markdown_content += "\n"

                # Save markdown file if level path exists
                if level_path:  
                    file_path = os.path.join(dir_path, level_path, f"{label.capitalize()}.md")
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "w") as f:
                        f.write(markdown_content)
                    print(f"✅ {label.capitalize()} saved in {file_path}")
                break

graph = Graph()
OntologyYaml.rdf_to_yaml(graph)


        
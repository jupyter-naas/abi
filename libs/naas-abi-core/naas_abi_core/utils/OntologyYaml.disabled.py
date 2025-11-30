import copy
import random

import pydash as _
from naas_abi import services
from rdflib import OWL, RDF, RDFS, Graph, URIRef

from naas_abi_core import logger


class OntologyYaml:
    def __init__(self):
        pass

    @staticmethod
    def rdf_to_yaml(
        graph,
        class_colors_mapping: dict = {},
        top_level_class: str = "http://purl.obolibrary.org/obo/BFO_0000001",
        display_relations_names: bool = True,
        yaml_properties: list = [],
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
            display_relations_names=display_relations_names,
            yaml_properties=yaml_properties,
        )


class Translator:
    def __init__(self):
        # Dictionary to store ontology components
        self.onto = {}
        self.onto_tuples = {}
        self.onto_prop = {}
        self.onto_oprop = {}
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
            OWL.AnnotationProperty,
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
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil": "nil",
        }

        # Add RDFS terms
        rdfs_terms = {
            "http://www.w3.org/2000/01/rdf-schema#domain": "domain",
            "http://www.w3.org/2000/01/rdf-schema#label": "label",
            "http://www.w3.org/2000/01/rdf-schema#range": "range",
            "http://www.w3.org/2000/01/rdf-schema#subClassOf": "subclassOf",
        }

        # Add OWL terms
        owl_terms = {
            "http://www.w3.org/2002/07/owl#complementOf": "complementOf",
            "http://www.w3.org/2002/07/owl#intersectionOf": "intersectionOf",
            "http://www.w3.org/2002/07/owl#inverseOf": "inverseOf",
            "http://www.w3.org/2002/07/owl#unionOf": "unionOf",
        }

        # Add SKOS terms
        skos_terms = {
            "http://www.w3.org/2004/02/skos/core#altLabel": "altLabel",
            "http://www.w3.org/2004/02/skos/core#definition": "definition",
            "http://www.w3.org/2004/02/skos/core#example": "example",
        }

        # Add DC terms
        dc_terms = {
            "http://purl.org/dc/elements/1.1/identifier": "identifier",
            "http://purl.org/dc/terms/title": "title",
            "http://purl.org/dc/terms/description": "description",
            "http://purl.org/dc/terms/license": "license",
            "http://purl.org/dc/terms/rights": "rights",
            "http://purl.org/dc/terms/contributor": "contributor",
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
            "unionOf": "or",
            "intersectionOf": "and",
            "complementOf": "not",
        }

    def translate(
        self,
        graph,
        class_colors_mapping,
        top_level_class,
        display_relations_names,
        yaml_properties,
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

        # Get individuals.
        self.load_individuals()

        # Map object properties labels
        self.map_oprop_labels()

        # Create the YAML file.
        return self.create_yaml(
            class_colors_mapping, display_relations_names, yaml_properties
        )

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
                self.onto[str(s)] = {"__id": str(s)}

            # If the predicate is not in the onto dict, we create a new list for it.
            # We create a list because there can be multiple values for the same predicate.
            if self.mapping[str(p)] not in self.onto[str(s)]:
                self.onto[str(s)][self.mapping[str(p)]] = []

            # We append the object to the list of the predicate.
            self.onto[str(s)][self.mapping[str(p)]].append(str(o))

    def load_classes(self):
        # We filter the classes from the ontology.
        _onto_classes = _.filter_(
            self.onto,
            lambda x: "http://www.w3.org/2002/07/owl#Class" in x["type"]
            if "type" in x
            else None,
        )

        # We remove the subclassOf that are restrictions to keep it simple for now.
        # TODO: Resolve the restrictions to be able to display/use them later on.
        for cls in _onto_classes:
            cls["subclassOf"] = _.filter_(
                cls.get("subclassOf", []), lambda x: True if "http" in x else False
            )

        # We re build a dictionary with the __id as the key as it is easier to access the data this way.
        self.onto_classes = {e["__id"]: e for e in _onto_classes}

    def __compute_class_levels(self, cls_id, level=0):
        if cls_id in self.onto_classes:
            self.onto_classes[cls_id]["level"] = level

            if level not in self.amount_per_level:
                self.amount_per_level[level] = 0

            self.amount_per_level[level] += 1

            subclassOf = _.filter_(
                self.onto_classes, lambda x: cls_id in x["subclassOf"]
            )

            for subclass in subclassOf:
                self.__compute_class_levels(subclass["__id"], level + 1)

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

            if str(a) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#first":
                first = str(b)

            if (
                str(a) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"
                and str(b) != "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"
            ):
                rest = str(b)
        return first, rest

    # get_linked_classes is a recursive function used for Object Properties ranges and domains.
    # It will build a tree of classes based on the unionOf, intersectionOf and complementOf.
    # It is usefull to understand what are the conditions for a class to be in the range or domain of an object property.
    def get_linked_classes(self, cls_id, rel_type=None):
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
                    for e in _.get(cls, "unionOf", [])
                ]
                + [
                    self.get_linked_classes(e, "intersectionOf")
                    for e in _.get(cls, "intersectionOf", [])
                ]
                + [
                    self.get_linked_classes(e, "complementOf")
                    for e in _.get(cls, "complementOf", [])
                ]
            )
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
                    if (
                        operator in right
                        and type(right[operator]) is dict
                        and operator in right[operator]
                        and type(right[operator][operator]) is list
                    ):
                        right[operator] = right[operator][operator]

                    return {operator: _.flatten([left[operator], right[operator]])}
                else:
                    return {operator: _.flatten([left, right])}
            else:
                return {operator: left}

    # We map the ranges and domains to the classes by calling get_linked_classes.
    def map_ranges_domains(self, x):
        if "range" in x:
            x["range"] = _.map_(
                x["range"],
                lambda x: x if "http" in x else self.get_linked_classes(x)[0],
            )
        if "domain" in x:
            x["domain"] = _.map_(
                x["domain"],
                lambda x: x if "http" in x else self.get_linked_classes(x)[0],
            )
        return x

    def load_object_properties(self):
        # We filter the object properties from the ontology.
        _onto_oprop = _.filter_(
            self.onto,
            lambda x: "http://www.w3.org/2002/07/owl#ObjectProperty" in x["type"]
            if "type" in x
            else None,
        )

        # For each Object property, we map the ranges and domains.
        for i in _onto_oprop:
            self.map_ranges_domains(i)

        # We re build a dictionary with the __id as the key as it is easier to access the data this way.
        self.onto_oprop = {e["__id"]: e for e in _onto_oprop}

    def load_individuals(self):
        self.onto_individuals = _.filter_(
            self.onto,
            lambda x: "http://www.w3.org/2002/07/owl#NamedIndividual" in x["type"]
            if "type" in x
            else None,
        )

    def map_oprop_labels(self):
        # Map Object properties with label
        self.mapping_oprop = {}
        for o in self.onto_oprop:
            if o and "label" in self.onto_oprop.get(o):
                self.mapping_oprop[o] = self.onto_oprop.get(o).get("label")[0]

    def create_yaml(
        self,
        class_color,
        display_relations_names,
        yaml_properties,
    ):
        # Init
        all_classes = {}
        classes = {}
        entities = []
        prefixes = {
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "abi": "http://ontology.naas.ai/abi/",
            "bfo": "http://purl.obolibrary.org/obo/",
            "cco": "https://www.commoncoreontologies.org/",
        }
        if len(yaml_properties) == 0:
            yaml_properties = [
                "definition",
                "example",
                "description",
                "download url",
                "asset url",
            ]

        # Loop on classes
        for onto_class in self.onto_classes:
            if onto_class.startswith("http"):
                onto_class_dict = self.onto_classes.get(onto_class)
                uid = onto_class_dict.get("__id")
                level = onto_class_dict.get("level", 0)
                label = ""
                if "label" in onto_class_dict:
                    label = onto_class_dict.get("label")[0]
                example = onto_class_dict.get("example", [])
                relations = onto_class_dict.get("relations", [])
                definition = onto_class_dict.get("definition", [])
                subclass = onto_class_dict.get("subclassOf", [])

                # Create title
                title = f"{label} (id: {uid})"
                if len(definition) > 0:
                    title = f"{title}\nDefinition: {', '.join(definition)}"
                if len(example) > 0:
                    title = f"{title}\nExamples: {'| '.join(example)}"
                if len(relations) > 0:
                    print(label, relations)
                    title = f"{title}\nRelations: {'| '.join(relations)}"
                title = f"{title}\n"

                # X position
                x = None
                entity_id = None
                color = "red"
                group = "TBD"
                if uid.startswith("http://purl.obolibrary.org/obo/"):
                    entity_id = uid.split("/obo/")[1]
                    color = "#97c1fb"
                    group = "BFO"
                elif uid.startswith("https://www.commoncoreontologies.org/"):
                    color = "#e4c51e"
                    group = "CCO"
                elif "/abi/" in uid:
                    color = "#48DD82"
                    group = "ABI"

                # Level 0: Entity
                if entity_id == "BFO_0000001":
                    x = 0
                # Level 1: Continuant
                elif entity_id == "BFO_0000002":
                    x = -500
                # Level 2
                elif entity_id == "BFO_0000004":
                    x = -1000
                elif entity_id == "BFO_0000031":
                    x = -600
                elif entity_id == "BFO_0000020":
                    x = -300
                # Level 3
                elif entity_id == "BFO_0000040":
                    x = -1100
                elif entity_id == "BFO_0000141":
                    x = -800
                elif entity_id == "BFO_0000019":
                    x = -400
                elif entity_id == "BFO_0000017":
                    x = -200
                # Level 4
                elif entity_id == "BFO_0000027":
                    x = -1700
                elif entity_id == "BFO_0000024":
                    x = -1500
                elif entity_id == "BFO_0000030":
                    x = -1300
                elif entity_id == "BFO_0000006":
                    x = -1100
                elif entity_id == "BFO_0000140":
                    x = -900
                elif entity_id == "BFO_0000029":
                    x = -700
                elif entity_id == "BFO_0000145":
                    x = -500
                elif entity_id == "BFO_0000023":
                    x = -300
                elif entity_id == "BFO_0000016":
                    x = -100
                # Level 5
                elif entity_id == "BFO_0000018":
                    x = -1300
                elif entity_id == "BFO_0000026":
                    x = -1200
                elif entity_id == "BFO_0000009":
                    x = -1100
                elif entity_id == "BFO_0000028":
                    x = -1000
                elif entity_id == "BFO_0000142":
                    x = -900
                elif entity_id == "BFO_0000146":
                    x = -800
                elif entity_id == "BFO_0000147":
                    x = -700
                elif entity_id == "BFO_0000034":
                    x = -100

                # Level 1: Occurent
                elif entity_id == "BFO_0000003":
                    x = 500
                # Level 2
                elif entity_id == "BFO_0000015":
                    x = 100
                elif entity_id == "BFO_0000035":
                    x = 400
                elif entity_id == "BFO_0000008":
                    x = 700
                elif entity_id == "BFO_0000011":
                    x = 1000
                # Level 3
                elif entity_id == "BFO_0000182":
                    x = 100
                elif entity_id == "BFO_0000038":
                    x = 600
                elif entity_id == "BFO_0000148":
                    x = 900
                # Level 4
                elif entity_id == "BFO_0000202":
                    x = 600
                elif entity_id == "BFO_0000203":
                    x = 900

                # Y position
                start_y = -1000
                margin_y = 250
                y = start_y + level * margin_y

                # Concat classes
                cl = {
                    "id": uid,
                    "name": label,
                    "definition": "| ".join(definition),
                    "example": "| ".join(example),
                    "style": {
                        "group": group,
                        "color": color,
                        "title": title,
                    },
                }
                if x is not None:
                    cl["style"]["x"] = x * 1.5
                    cl["style"]["y"] = y * 1.5
                    cl["style"]["fixed"] = True

                if len(subclass) > 0:
                    cl["relations"] = [{"label": "is_a", "to": subclass[0]}]
                all_classes[uid] = cl

                # Add BFO Classes by default
                if "BFO_" in uid:
                    classes[uid] = cl

        logger.debug(f"All classes: {len(all_classes)}")
        logger.debug(f"BFO classes: {len(classes)}")

        # Loop on individuals
        for individual in self.onto_individuals:
            # Init variables
            uri = individual.get("__id")  # Get URI
            if len(individual.get("label", [])) > 0:
                label = individual.get("label")[0]  # Get label
            else:
                label = uri.split("/")[-1]
            class_uri = [
                i for i in individual.get("type", []) if "NamedIndividual" not in i
            ][0]  # Get class
            if "/abi/" in uri:
                # Assign random color for a new class
                if class_uri not in class_color:
                    random_color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
                    class_color[class_uri] = random_color
                color = class_color[class_uri]

                # Create entity: individuals, classes and subclassof relations
                entity = {
                    "id": uri,
                    "name": label,
                    "class": class_uri,
                    "relations": [],
                    "style": {
                        "color": color,
                    },
                }

                # Add image url
                image_url = (
                    individual.get("picture")
                    or individual.get("logo")
                    or individual.get("avatar")
                )
                if image_url:
                    for i in image_url:
                        if str(i) != "None" and str(i).startswith("http"):
                            entity["style"]["image"] = i
                            entity["style"]["shape"] = "image"
                            break

                # Add ontology group
                ontology_group = individual.get("ontology group")
                if ontology_group:
                    entity["style"]["group"] = ontology_group[0]

                # Add coordinates
                coordinate_x = individual.get("x")
                coordinate_y = individual.get("y")
                if coordinate_x and coordinate_y:
                    entity["style"]["x"] = coordinate_x
                    entity["style"]["y"] = coordinate_y
                    entity["style"]["fixed"] = True

                # Create entity relations between individuals
                entity_relations = entity.get("relations")
                for r in self.mapping_oprop.values():
                    if r in individual:
                        for v in individual.get(r):
                            entity_relations.append(
                                {
                                    "label": r if display_relations_names else None,
                                    "to": v,
                                }
                            )

                # Add data properties
                for x in yaml_properties:
                    x_value = individual.get(x)
                    if x_value:
                        entity[x] = x_value[0]

                # Concat entities with individual
                entities.append(entity)

                # YAML: Add class to dict entities (to be displayed)
                class_x = copy.deepcopy(class_uri)
                while True:
                    # YAML: Add class to dict classes
                    if class_x in classes:
                        break
                    class_dict = all_classes.get(class_x)
                    if class_dict is None:
                        logger.debug(f"🛑 Class '{class_x}' does not exist!")
                        break
                    classes[class_x] = class_dict
                    logger.debug(f"✅ Class '{class_x}' added to entities!", class_dict)

                    # Check if BFO
                    if "BFO_" in class_dict.get("id"):
                        break
                    class_x = _.get(class_dict, "relations[0].to")

        def replace_values(data, old_value, new_value):
            if isinstance(data, list):
                for i, item in enumerate(data):
                    data[i] = replace_values(item, old_value, new_value)
            elif isinstance(data, dict):
                for key, value in data.items():
                    data[key] = replace_values(value, old_value, new_value)
            elif isinstance(data, str) and old_value in data:
                return data.replace(old_value, new_value)
            return data

        for p in prefixes:
            yaml_entities = replace_values(entities, prefixes.get(p), f"{p}:")
            yaml_classes = replace_values(
                list(classes.values()), prefixes.get(p), f"{p}:"
            )

        # Init
        yaml_data = {}
        yaml_data["prefixes"] = prefixes
        yaml_data["classes"] = yaml_classes
        yaml_data["entities"] = yaml_entities
        return yaml_data

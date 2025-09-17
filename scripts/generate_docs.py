from src import services
from rdflib import RDFS, URIRef
import pydash
import os
import urllib.parse
from abi import logger
import shutil
import json

ONTOLOGY_DICT: dict[str, str] = {
    "abi": "http://ontology.naas.ai/abi/",
    "bfo": "http://purl.obolibrary.org/obo/",
    "cco": "https://www.commoncoreontologies.org/",
    "attack": "http://w3id.org/sepses/vocab/ref/attack#",
    "d3fend": "http://d3fend.mitre.org/ontologies/d3fend.owl#",
}

ONTOLOGY_OPERATORS: dict[str, str] = {
    "unionOf": "or",
    "intersectionOf": "and",
    "complementOf": "not",
}

# Add standard RDF terms
rdf_terms: dict[str, str] = {
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "type",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#first": "first",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest": "rest",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil": "nil",
}

# Add RDFS terms
rdfs_terms: dict[str, str] = {
    "http://www.w3.org/2000/01/rdf-schema#domain": "domain",
    "http://www.w3.org/2000/01/rdf-schema#label": "label",
    "http://www.w3.org/2000/01/rdf-schema#range": "range",
    "http://www.w3.org/2000/01/rdf-schema#subClassOf": "subclassOf",
}

# Add OWL terms
owl_terms: dict[str, str] = {
    "http://www.w3.org/2002/07/owl#complementOf": "complementOf",
    "http://www.w3.org/2002/07/owl#intersectionOf": "intersectionOf",
    "http://www.w3.org/2002/07/owl#inverseOf": "inverseOf",
    "http://www.w3.org/2002/07/owl#unionOf": "unionOf",
}

# Add SKOS terms
skos_terms: dict[str, str] = {
    "http://www.w3.org/2004/02/skos/core#altLabel": "altLabel",
    "http://www.w3.org/2004/02/skos/core#definition": "definition",
    "http://www.w3.org/2004/02/skos/core#example": "example",
}

# Add DC terms
dc_terms: dict[str, str] = {
    "http://purl.org/dc/elements/1.1/identifier": "identifier",
    "http://purl.org/dc/terms/title": "title",
    "http://purl.org/dc/terms/description": "description",
    "http://purl.org/dc/terms/license": "license",
    "http://purl.org/dc/terms/rights": "rights",
    "http://purl.org/dc/terms/contributor": "contributor",
}

class OntologyDocs:
    def __init__(self):
        # Dictionary to store ontology components
        self.onto: dict = {}
        self.onto_tuples: dict = {}
        self.onto_oprop: dict = {}
        self.onto_dprop: dict = {}
        self.onto_classes: dict = {}
        self.amount_per_level: dict = {}
        self.mapping_oprop: dict = {}
        self.ontologies_dict: dict = ONTOLOGY_DICT
        self.operators: dict = ONTOLOGY_OPERATORS
        # Add pydash as instance variable
        self._ = pydash
        self.docs_ontology = os.path.join("docs", "ontology")

    def rdf_to_md(self):
        """Translate RDF graph to YAML.

        Args:
            graph (Graph): RDF graph to translate.
            top_level_class (str): Top level class to compute class levels.
        """
        # Load the ontology schemas.
        self.ontology_schemas = services.triple_store_service.get_schema_graph()

        # Load the mapping.
        self.load_mapping()

        # Extract triples from the Graph.
        self.load_triples()

        # Load the classes from the ontology.
        self.load_classes()

        # Compute class levels for the hierarchy building.
        self.amount_per_level = {}
        self.compute_class_levels(
            "http://purl.obolibrary.org/obo/BFO_0000001",
            level=0,
            level_path="Entity",
            hierarchy=[
                {
                    "uri": "http://purl.obolibrary.org/obo/BFO_0000001",
                    "label": "Entity",
                    "level": 0,
                    "level_path": "Entity",
                }
            ],
        )

        # Got object properties.
        self.load_object_properties()

        # Got data properties.
        self.load_data_properties()

        # Save ontology data as JSON
        self.save_json()

        # Create the YAML file.
        self.create_md()

    def load_mapping(self):
        # Init mapping
        mapping = {}
        for s, p, o in self.ontology_schemas.triples((None, RDFS.label, None)):
            if isinstance(s, URIRef):
                mapping[str(s)] = str(o)

        # Update mapping with all terms
        mapping.update(rdf_terms)
        mapping.update(rdfs_terms)
        mapping.update(owl_terms)
        mapping.update(skos_terms)
        mapping.update(dc_terms)
        self.mapping = mapping

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

    def load_triples(self):
        """Load the triples from the graph into the ontology dictionary.

        Args:
            graph (_type_): _description_
        """
        # Load the triples from the graph into the ontology dictionary.
        for s, p, o in self.ontology_schemas:
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
        _onto_classes = sorted(self._.filter_(
            self.onto,
            lambda x: "http://www.w3.org/2002/07/owl#Class" in x["type"]
            if "type" in x
            else None,
        ), key=lambda x: x["__id"])
        logger.info(f"🔍 Found {len(_onto_classes)} classes in the ontology.")

        # We remove the subclassOf that are restrictions to keep it simple for now.
        # TODO: Resolve the restrictions to be able to display/use them later on.
        for cls in _onto_classes:
            cls["subclassOf"] = self._.filter_(
                cls.get("subclassOf", []), lambda x: True if "http" in x else False
            )

        # We re build a dictionary with the __id as the key as it is easier to access the data this way.
        self.onto_classes = {e["__id"]: e for e in _onto_classes}

    def compute_class_levels(self, cls_id, level, level_path, hierarchy):
        if cls_id in self.onto_classes:
            self.onto_classes[cls_id]["level"] = level
            self.onto_classes[cls_id]["level_path"] = level_path
            self.onto_classes[cls_id]["hierarchy"] = hierarchy

            if level not in self.amount_per_level:
                self.amount_per_level[level] = 0

            self.amount_per_level[level] += 1

            subclassOf = self._.filter_(
                self.onto_classes, lambda x: cls_id in x["subclassOf"]
            )
            for subclass in subclassOf:
                class_uri = subclass["__id"]
                class_label = (
                    subclass["label"][0].capitalize().replace("/", "-").strip()
                )
                class_level = level + 1
                class_level_path = os.path.join(level_path, class_label)
                self.compute_class_levels(
                    class_uri,
                    class_level,
                    class_level_path,
                    hierarchy
                    + [
                        {
                            "uri": class_uri,
                            "label": class_label,
                            "level": class_level,
                            "level_path": class_level_path,
                        }
                    ],
                )

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
        # Handle None case
        if cls_id is None:
            return []
        
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

                    return {operator: self._.flatten([left[operator], right[operator]])}
                else:
                    return {operator: self._.flatten([left, right])}
            else:
                return {operator: left}

    # We map the ranges and domains to the classes by calling get_linked_classes.
    def map_ranges_domains(self, x):
        if "domain" in x:
            x["domain"] = self._.map_(
                x["domain"],
                lambda x: x if (x is not None and "http" in x) else (self.get_linked_classes(x)[0] if self.get_linked_classes(x) else None),
            )
        if "range" in x:
            x["range"] = self._.map_(
                x["range"],
                lambda x: x if (x is not None and "http" in x) else (self.get_linked_classes(x)[0] if self.get_linked_classes(x) else None),
            )
        return x

    def load_object_properties(self):
        # We filter the object properties from the ontology.
        _onto_oprop = self._.filter_(
            self.onto,
            lambda x: "http://www.w3.org/2002/07/owl#ObjectProperty" in x["type"]
            if "type" in x
            else None,
        )
        logger.info(f"🔍 Found {len(_onto_oprop)} object properties in the ontology.")

        # For each Object property, we map the ranges and domains.
        for i in _onto_oprop:
            self.map_ranges_domains(i)

        # We re build a dictionary with the __id as the key as it is easier to access the data this way.
        self.onto_oprop = {e["__id"]: e for e in _onto_oprop}

    def load_data_properties(self):
        # We filter the data properties from the ontology.
        _onto_dprop = self._.filter_(
            self.onto,
            lambda x: "http://www.w3.org/2002/07/owl#DatatypeProperty" in x["type"]
            if "type" in x
            else None,
        )
        logger.info(f"🔍 Found {len(_onto_dprop)} data properties in the ontology.")

        # We re build a dictionary with the __id as the key as it is easier to access the data this way.
        self.onto_dprop = {e["__id"]: e for e in _onto_dprop}

    def save_json(self):
        """Save ontology data as JSON.

        Returns:
            dict: Dictionary containing ontology data structures
        """
        # Create the docs/ontology/reference/model directory if it doesn't exist
        os.makedirs("docs/ontology/reference/model", exist_ok=True)

        # Save the ontology data as JSON
        with open("docs/ontology/reference/model/ontology.json", "w") as f:
            json.dump(self.onto, f, indent=4, ensure_ascii=False)

        logger.info(f"💾 Saving onto_tuples.json: {len(self.onto_tuples)}")
        with open("docs/ontology/reference/model/onto_tuples.json", "w") as f:
            json.dump(self.onto_tuples, f, indent=4, ensure_ascii=False)

        logger.info(f"💾 Saving onto_classes.json: {len(self.onto_classes)}")
        with open("docs/ontology/reference/model/onto_classes.json", "w") as f:
            json.dump(self.onto_classes, f, indent=4, ensure_ascii=False)

        logger.info(f"💾 Saving onto_oprop.json: {len(self.onto_oprop)}")
        with open("docs/ontology/reference/model/onto_oprop.json", "w") as f:
            json.dump(self.onto_oprop, f, indent=4, ensure_ascii=False)

        logger.info(f"💾 Saving onto_dprop.json: {len(self.onto_dprop)}")
        with open("docs/ontology/reference/model/onto_dprop.json", "w") as f:
            json.dump(self.onto_dprop, f, indent=4, ensure_ascii=False)

        with open("docs/ontology/reference/model/amount_per_level.json", "w") as f:
            json.dump(self.amount_per_level, f, indent=4, ensure_ascii=False)

    def create_md(self):
        # Init
        reference_dir = os.path.join(self.docs_ontology, "reference")
        shutil.rmtree(reference_dir, ignore_errors=True)
        foundry_dir = os.path.join(self.docs_ontology, "foundry")
        shutil.rmtree(foundry_dir, ignore_errors=True)
        folder = "full"
        dir_path = os.path.join(reference_dir, folder)
        onto_classes = self.onto_classes.values()
        logger.info(f"Foundry classes : {len(onto_classes)}")

        # Loop on classes
        for onto_class in onto_classes:
            onto_class = onto_class.get("__id")
            if onto_class.startswith("http"):
                onto_class_dict = self.onto_classes.get(onto_class)
                logger.info(f"==> Onto class : {onto_class}")
                level = onto_class_dict.get("level", 0)
                level_path = onto_class_dict.get("level_path", "Not Defined")
                curated_in_foundry = onto_class_dict.get("is curated in foundry", [])

                # H1 : Title
                label = onto_class_dict.get("label", [""])[0]
                markdown_content = f"# {label.capitalize()}\n\n"

                # H2 : Overview
                markdown_content += "## Overview\n\n"

                # H3 : Definition
                markdown_content += "### Definition\n"
                definition = onto_class_dict.get("definition", [])
                if definition:
                    markdown_content += "\n".join(definition) + "\n\n"
                else:
                    markdown_content += "Not defined.\n\n"

                #  H3 : Examples
                markdown_content += "### Examples\n"
                example = onto_class_dict.get("example", [])
                if len(example) > 1:
                    markdown_content += "\n".join(f"- {ex}" for ex in example) + "\n\n"
                elif len(example) == 1:
                    markdown_content += f"{example[0]}\n\n"
                else:
                    markdown_content += "Not defined.\n\n"

                # H3 : Aliases
                markdown_content += "### Aliases\n"
                aliases = onto_class_dict.get("altLabel", [])
                if len(aliases) > 1:
                    markdown_content += (
                        "\n".join(f"- {alias}" for alias in aliases) + "\n\n"
                    )
                elif len(aliases) == 1:
                    markdown_content += f"{aliases[0]}\n\n"
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
                hierarchy = onto_class_dict.get("hierarchy", [])
                if len(hierarchy) == 0:
                    markdown_content += "Not defined.\n\n"
                else:
                    markdown_content += "```mermaid\n"
                    markdown_content += "graph BT\n"
                    nodes = []
                    safe_name_init = hierarchy[0].get("uri").split("/")[-1]
                    formatted_label_init = (
                        hierarchy[0].get("label").replace(" ", "<br>")
                    )
                    for k, v in self.ontologies_dict.items():
                        if v in hierarchy[0].get("uri"):
                            ontology_init = k
                            break
                    nodes.append(
                        f"    {safe_name_init}({formatted_label_init}):::{ontology_init}\n"
                    )

                    # Create nodes and connections
                    for i, level in enumerate(hierarchy[1:], 1):
                        uri = level.get("uri")
                        for k, v in self.ontologies_dict.items():
                            if v in uri:
                                ontology = k
                                break
                        safe_name = uri.split("/")[-1]
                        parent_name = (
                            hierarchy[i - 1].get("uri").split("/")[-1]
                            if i > 1
                            else safe_name_init
                        )
                        formatted_label = level.get("label").replace(" ", "<br>")
                        nodes.append(
                            f"    {safe_name}({formatted_label}):::{ontology}-->{parent_name}\n"
                        )

                    # Add nodes to markdown
                    markdown_content += "".join(reversed(nodes))

                    # Add styling
                    markdown_content += "    \n"
                    markdown_content += "    classDef bfo fill:#97c1fb,color:#060606\n"
                    markdown_content += "    classDef cco fill:#e4c51e,color:#060606\n"
                    markdown_content += "    classDef abi fill:#48DD82,color:#060606\n"
                    markdown_content += "```\n\n"
                    for h in hierarchy:
                        h_label = h.get("label")
                        h_level_path = h.get("level_path")
                        h_file_path = urllib.parse.quote(
                            os.path.join("/", dir_path, h_level_path, h_label + ".md")
                        )
                        markdown_content += f"- [{h_label}]({h_file_path})\n"
                    markdown_content += "\n\n"

                # H3 : Ontology Reference
                markdown_content += "### Ontology Reference\n"

                # Get the ontology reference
                ontology_reference = "Not defined."
                for k, v in self.ontologies_dict.items():
                    if v in onto_class:
                        ontology_reference = f"[{k}]({v})"
                        break

                # Get the sub ontology reference (CCO)
                sub_ontology_reference_label = ""
                sub_ontology_reference = onto_class_dict.get(
                    "is curated in ontology", []
                )
                if sub_ontology_reference:
                    sub_ontology_reference_name = sub_ontology_reference[0].split("/")[
                        -1
                    ]
                    sub_ontology_reference_label = f": [{sub_ontology_reference_name}]({sub_ontology_reference[0]})"

                # Add the ontology reference and the sub ontology reference
                markdown_content += (
                    f"- {ontology_reference}{sub_ontology_reference_label}\n"
                )
                markdown_content += "\n"

                # H2 : Properties
                markdown_content += "## Properties\n"
                parents = [h["uri"] for h in hierarchy]

                # H3 : Data Properties
                dproperties = self._.filter_(
                    self.onto_dprop.values(),
                    lambda x: "domain" in x
                    and any(uri in x["domain"] for uri in parents),
                )
                data_properties = []
                for dprop in sorted(dproperties, key=lambda x: x.get("__id", 0)):
                    d_predicate = dprop.get("__id", "")
                    d_label = dprop.get("label", [""])[0]
                    d_definition = dprop.get("definition", [""])[0]
                    d_example = dprop.get("example", [""])[0]
                    d_domain = dprop.get("domain")
                    if isinstance(d_domain, list):
                        d_domain_uri = d_domain[0]
                        d_domain_class_dict = self._.filter_(
                            self.onto_classes.values(),
                            lambda x: x["__id"] == d_domain_uri,
                        )[0]
                        d_domain_label = d_domain_class_dict.get("label", [""])[0]
                        d_domain_level_path = d_domain_class_dict.get("level_path", "")
                        d_domain_level = d_domain_class_dict.get("level", 0)
                    else:
                        d_domain_uri = ""
                        d_domain_label = ""
                        d_domain_level = 0
                        d_domain_level_path = ""
                    d_range = dprop.get("range")
                    if isinstance(d_range, list):
                        d_range_uri = d_range[0]
                        d_range_label = d_range_uri.split("#")[-1]
                    else:
                        d_range_uri = ""
                        d_range_label = ""
                    data_properties.append(
                        {
                            "property": {"uri": d_predicate, "label": d_label},
                            "definition": d_definition,
                            "example": d_example,
                            "domain": {
                                "uri": d_domain_uri,
                                "label": d_domain_label,
                                "level_path": d_domain_level_path,
                            },
                            "range": {"uri": d_range_uri, "label": d_range_label},
                            "level": d_domain_level,
                        }
                    )

                if len(data_properties) > 0:
                    markdown_content += "### Data Properties\n"
                    markdown_content += (
                        "| Ontology | Label | Definition | Example | Domain | Range |\n"
                    )
                    markdown_content += (
                        "|----------|-------|------------|---------|--------|-------|\n"
                    )
                    for dprop in sorted(
                        data_properties, key=lambda x: x.get("level", 0)
                    ):
                        dprop_label = dprop.get("property", {}).get("label")
                        dprop_uri = dprop.get("property", {}).get("uri")
                        for k, v in self.ontologies_dict.items():
                            if v in dprop_uri:
                                dprop_domain_ontology = k
                                break
                        dprop_definition = dprop.get("definition")
                        dprop_example = dprop.get("example")
                        dprop_domain = dprop.get("domain", {}).get("label")
                        dprop_domain_level_path = urllib.parse.quote(
                            os.path.join(
                                "/",
                                dir_path,
                                dprop.get("domain", {}).get("level_path"),
                                dprop.get("domain", {}).get("label").capitalize()
                                + ".md",
                            )
                        )
                        dprop_range = dprop.get("range", {}).get("label")
                        dprop_range_uri = dprop.get("range", {}).get("uri")
                        markdown_content += f"| {dprop_domain_ontology} | [{dprop_label}]({dprop_uri}) | {dprop_definition} | {dprop_example} | [{dprop_domain}]({dprop_domain_level_path}) | [{dprop_range}]({dprop_range_uri}) |\n"
                    markdown_content += "\n"

                # H3 : Object Properties
                oproperties = self._.filter_(
                    self.onto_oprop.values(),
                    lambda x: "domain" in x
                    and any(uri in x["domain"] for uri in parents),
                )
                object_properties = []
                for oprop in sorted(oproperties, key=lambda x: x.get("__id", 0)):
                    o_uri = oprop.get("__id", "")
                    o_label = oprop.get("label", [""])[0]
                    o_definition = oprop.get("definition", [""])[0]
                    o_example = oprop.get("example", [""])[0]
                    o_domain = oprop.get("domain")
                    if isinstance(o_domain, list):
                        o_domain_uri = o_domain[0]
                        o_domain_class_dict = self._.filter_(
                            self.onto_classes.values(),
                            lambda x: x["__id"] == o_domain_uri,
                        )[0]
                        o_domain_label = o_domain_class_dict.get("label", [""])[0]
                        o_domain_level_path = o_domain_class_dict.get("level_path", "")
                        o_domain_level = o_domain_class_dict.get("level", 0)
                    else:
                        o_domain_uri = str(o_domain)
                        o_domain_label = str(o_domain)
                        o_domain_level = 0
                        o_domain_level_path = ""

                    o_range = oprop.get("range")
                    if isinstance(o_range, list):
                        o_range_uri = o_range[0]
                        o_range_class_dict = self._.filter_(
                            self.onto_classes.values(),
                            lambda x: x["__id"] == o_range_uri,
                        )
                        if len(o_range_class_dict) > 0:
                            o_range_class_dict = o_range_class_dict[0]
                            o_range_label = o_range_class_dict.get("label", [""])[0]
                            o_range_level_path = o_range_class_dict.get(
                                "level_path", ""
                            )
                        else:
                            o_range_label = str(o_range[0])
                            o_range_level_path = str(o_range[0])
                    else:
                        o_range_uri = str(o_range)
                        o_range_label = str(o_range)
                    o_inverse_of = oprop.get("inverseOf")
                    if isinstance(o_inverse_of, list):
                        o_inverse_of_uri = o_inverse_of[0]
                        o_inverse_of_class_dict = self._.filter_(
                            self.onto_oprop.values(),
                            lambda x: x["__id"] == o_inverse_of_uri,
                        )
                        if len(o_inverse_of_class_dict) > 0:
                            o_inverse_of_class_dict = o_inverse_of_class_dict[0]
                            o_inverse_of_label = o_inverse_of_class_dict.get(
                                "label", [""]
                            )[0]
                        else:
                            o_inverse_of_label = ""
                    else:
                        o_inverse_of_uri = ""
                        o_inverse_of_label = ""
                    object_properties.append(
                        {
                            "property": {"uri": o_uri, "label": o_label},
                            "definition": o_definition,
                            "example": o_example,
                            "domain": {
                                "uri": o_domain_uri,
                                "label": o_domain_label,
                                "level_path": o_domain_level_path,
                            },
                            "range": {
                                "uri": o_range_uri,
                                "label": o_range_label,
                                "level_path": o_range_level_path,
                            },
                            "inverseOf": {
                                "uri": o_inverse_of_uri,
                                "label": o_inverse_of_label,
                            },
                            "level": o_domain_level,
                        }
                    )

                if len(object_properties) > 0:
                    markdown_content += "### Object Properties\n"
                    markdown_content += "| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |\n"
                    markdown_content += "|----------|-------|------------|---------|--------|-------|------------|\n"
                    for oprop in sorted(
                        object_properties, key=lambda x: x.get("level", 0)
                    ):
                        oprop_label = oprop.get("property", {}).get("label")
                        oprop_uri = oprop.get("property", {}).get("uri")
                        oprop_ontology = ""
                        for k, v in self.ontologies_dict.items():
                            if v in oprop_uri:
                                oprop_ontology = k
                                break
                        oprop_definition = oprop.get("definition")
                        oprop_example = oprop.get("example")
                        oprop_domain = oprop.get("domain", {}).get("label")
                        _ = oprop.get("domain", {}).get("uri")
                        oprop_domain_level_path = urllib.parse.quote(
                            os.path.join(
                                "/",
                                dir_path,
                                oprop.get("domain", {}).get("level_path"),
                                oprop.get("domain", {}).get("label").capitalize()
                                + ".md",
                            )
                        )
                        oprop_range = oprop.get("range", {}).get("label")
                        _ = oprop.get("range", {}).get("uri")
                        oprop_range_level_path = urllib.parse.quote(
                            os.path.join(
                                "/",
                                dir_path,
                                oprop.get("range", {}).get("level_path"),
                                oprop.get("range", {}).get("label").capitalize()
                                + ".md",
                            )
                        )
                        oprop_inverse_of = oprop.get("inverseOf", {}).get("label")
                        oprop_inverse_of_uri = oprop.get("inverseOf", {}).get("uri")
                        markdown_content += f"| {oprop_ontology} | [{oprop_label}]({oprop_uri}) | {oprop_definition} | {oprop_example} | [{oprop_domain}]({oprop_domain_level_path}) | [{oprop_range}]({oprop_range_level_path}) | [{oprop_inverse_of}]({oprop_inverse_of_uri}) |\n"
                    markdown_content += "\n"

                # Save markdown file if level path exists
                if level_path:
                    # Save markdown in model folder
                    label_safe = label.capitalize().replace("/", "-").strip()
                    file_path = os.path.join(dir_path, level_path, f"{label_safe}.md")
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "w") as f:
                        f.write(markdown_content)
                    logger.info(f"✅ {label.capitalize()} saved in {file_path}")

                    # Save markdown ontology folder
                    for k, v in self.ontologies_dict.items():
                        if v in onto_class:
                            # ontology_path = os.path.join(reference_dir, k)
                            # file_ontology_path = os.path.join(
                            #     ontology_path, level_path, f"{label_safe}.md"
                            # )
                            # os.makedirs(
                            #     os.path.dirname(file_ontology_path), exist_ok=True
                            # )
                            # shutil.copy(file_path, file_ontology_path)
                            # logger.info(
                            #     f"✅ {label.capitalize()} saved in {file_ontology_path}"
                            # )

                            # Create Ontology Slim
                            ontology_slim_path = os.path.join(reference_dir, k)
                            if len(level_path.split("/")) < 3:
                                continue
                            if "Process boundary" in level_path or "Process profile" in level_path:
                                continue

                            level_slim_path = "/".join(level_path.split("/")[1:3])
                            for word in ["Specifically dependent continuant", "Independent continuant"]:
                                if word in level_path and not level_path.endswith(word) and len(level_path.split("/")) > 3:
                                    slim_level = level_path.split("/")[3:4][0]
                                    level_slim_path = level_slim_path.replace(word, slim_level)
                                    break
                                elif word in level_path and level_path.endswith(word):
                                    level_slim_path = None
                            if level_slim_path is None:
                                continue
                            abi_slim_path = os.path.join(
                                ontology_slim_path, level_slim_path, f"{label_safe}.md"
                            )
                            os.makedirs(
                                os.path.dirname(abi_slim_path), exist_ok=True
                            )
                            shutil.copy(file_path, abi_slim_path)
                            logger.info(
                                f"✅ {label.capitalize()} saved in {abi_slim_path}"
                            )
                            break

                    # Add curated in foundry to the markdown content
                    if curated_in_foundry:
                        for foundry in curated_in_foundry:
                            foundry_path = os.path.join(
                                "docs", "ontology", "foundry", foundry
                            )
                            file_foundry_path = os.path.join(
                                foundry_path, level_slim_path, f"{label_safe}.md"
                            )
                            os.makedirs(
                                os.path.dirname(file_foundry_path), exist_ok=True
                            )
                            shutil.copy(file_path, file_foundry_path)
                            logger.info(
                                f"✅ {label.capitalize()} saved in {file_foundry_path}"
                            )

if __name__ == "__main__":  
    OntologyDocs().rdf_to_md()

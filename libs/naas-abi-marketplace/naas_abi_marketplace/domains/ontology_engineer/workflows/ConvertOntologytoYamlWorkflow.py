"""
Convert Turtle (TTL) ontology file to Pyvis network visualization and/or YAML format.

This script parses a Turtle ontology file, extracts owl:Class entities,
their labels, and relationships defined through restrictions, then can create
an interactive Pyvis network visualization (HTML/PNG) and/or YAML format.

Usage:
    uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology-engineer/ontologies/convert_ontology.py [OPTIONS]
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated, List, Optional, Tuple

import yaml
from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from naas_abi_marketplace.applications.naas.workflows.CreateWorkspaceOntologyWorkflow import (
    CreateWorkspaceOntologyWorkflow,
    CreateWorkspaceOntologyWorkflowConfiguration,
    CreateWorkspaceOntologyWorkflowParameters,
)
from naas_abi_marketplace.domains.ontology_engineer.utils.graph import (
    get_class_id_prefix,
    get_group_from_class_hierarchy,
    get_inverse_property,
    get_rdfs_label,
    get_short_name,
    parse_turtle_ontology,
)
from pydantic import Field
from rdflib import OWL, RDF, RDFS, SKOS, URIRef

GROUP_TO_STYLE: dict = {
    "WHAT": {
        "shape": "diamond",
        "color": "purple",
        # "image": "https://api.naas.ai/workspace/96ce7ee7-e5f5-4bca-acf9-9d5d41317f81/asset/88fb7cc7-091b-4f9f-93f0-33d1f7cafaa9/object",
    },
    "WHEN": {"shape": "diamond", "color": "#d63384"},
    "WHO": {"shape": "diamond", "color": "#0d6efd"},
    "WHERE": {"shape": "diamond", "color": "#6c757d"},
    "HOW WE KNOW": {"shape": "diamond", "color": "#0dcaf0"},
    "HOW IT IS": {"shape": "diamond", "color": "#20c997"},
    "WHY": {"shape": "diamond", "color": "#198754"},
    "UNKNOWN": {"shape": "diamond", "color": "purple"},
}


@dataclass
class ConvertOntologytoYamlWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for Convert Ontology to YAML Workflow.

    Attributes:
        default_output_dir (Optional[str]): Default output directory for YAML files
    """

    create_workspace_ontology_config: CreateWorkspaceOntologyWorkflowConfiguration
    default_output_dir: Optional[str] = None


class ConvertOntologytoYamlWorkflowParameters(WorkflowParameters):
    """Parameters for Convert Ontology to YAML Workflow.

    Attributes:
        turtle_path (str): Path to the Turtle (.ttl) file
        output_dir (Optional[str]): Optional output directory. If not provided, uses the
                                    directory of the turtle_path
        imported_ontologies (Optional[List[str]]): Optional list of additional ontology paths/URLs to import
    """

    turtle_path: Annotated[
        str, Field(..., description="Path to the Turtle (.ttl) file")
    ]
    output_dir: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional output directory. If not provided, uses the directory of the turtle_path",
        ),
    ] = None
    imported_ontologies: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="Optional list of additional ontology paths/URLs to import",
        ),
    ] = None
    publish_to_workspace: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to publish the ontology to a workspace. If True, the ontology will be published to a workspace using the CreateWorkspaceOntologyWorkflow.",
        ),
    ] = False
    ontology_name: Annotated[
        str,
        Field(
            default="New Ontology",
            description="The name of the ontology to publish to the workspace.",
        ),
    ] = "New Ontology"
    display_individuals_classes: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to display individuals and classes in the YAML file.",
        ),
    ] = True


class ConvertOntologytoYamlWorkflow(Workflow):
    """Workflow for converting Turtle ontology files to YAML format."""

    __configuration: ConvertOntologytoYamlWorkflowConfiguration

    def __init__(
        self,
        configuration: ConvertOntologytoYamlWorkflowConfiguration,
    ):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__create_workspace_ontology_workflow = CreateWorkspaceOntologyWorkflow(
            self.__configuration.create_workspace_ontology_config
        )

    def convert_ontology_to_yaml(
        self, parameters: ConvertOntologytoYamlWorkflowParameters
    ) -> str:
        """
        Convert a Turtle ontology file to YAML format.

        Args:
            parameters: Parameters containing the turtle_path, output_dir, and imported_ontologies.

        Returns:
            str: Path to the generated YAML file
        """
        try:
            if yaml is None:
                raise ImportError(
                    "PyYAML is required for YAML export. Install it with: pip install pyyaml"
                )

            turtle_path = parameters.turtle_path
            output_dir = (
                parameters.output_dir or self.__configuration.default_output_dir
            )
            imported_ontologies = parameters.imported_ontologies

            turtle_path_obj = Path(turtle_path)
            if not turtle_path_obj.exists():
                raise FileNotFoundError(f"Turtle file not found: {turtle_path}")

            # Determine output directory
            if output_dir is None:
                output_dir_path = turtle_path_obj.parent
            else:
                output_dir_path = Path(output_dir)
                output_dir_path.mkdir(parents=True, exist_ok=True)

            # Parse turtle and extract classes/relationships
            graph, imported_graph, classes_set, unique_relationships = (
                parse_turtle_ontology(turtle_path, imported_ontologies)
            )
            full_graph = graph + imported_graph

            # Convert classes set to dict for compatibility
            classes: dict = {class_uri: {} for class_uri in classes_set}

            # Extract all NamedIndividuals from the graph
            logger.info("Extracting owl:NamedIndividual instances...")
            named_individuals: dict[URIRef, List[URIRef]] = {}
            for individual_uri in graph.subjects(RDF.type, OWL.NamedIndividual):
                if isinstance(individual_uri, URIRef):
                    # Get the class type(s) of this individual (excluding owl:NamedIndividual)
                    types = [
                        t
                        for t in graph.objects(individual_uri, RDF.type)
                        if isinstance(t, URIRef) and t != OWL.NamedIndividual
                    ]
                    if types:
                        # Use the first type as the main class
                        class_type = types[0]
                        if class_type not in named_individuals:
                            named_individuals[class_type] = []
                        named_individuals[class_type].append(individual_uri)

            total_individuals = sum(len(v) for v in named_individuals.values())
            logger.info(
                f"Found {total_individuals} NamedIndividuals across {len(named_individuals)} classes"
            )

            # Extract class information and relationships
            yaml_classes: list = []
            yaml_entities: list = []

            # Global structure to track NamedIndividual relationships for inverse deduplication
            # Maps (source_id, target_id) -> (property_label, property_uri)
            individual_relationships_seen: dict[
                Tuple[str, str], Tuple[str, URIRef]
            ] = {}

            # Helper function to create individual entity entry
            def create_individual_entry(
                individual_uri: URIRef,
                class_uri: Optional[URIRef],
                individual_name: str,
                individual_id: str,
                individual_group: str,
                subclassof_uri: Optional[URIRef],
                entity_class: Optional[str] = None,
                include_class_relation: bool = True,
            ) -> dict:
                """Create an entity entry for a NamedIndividual."""
                style: dict = {"group": individual_group}
                if "image" in GROUP_TO_STYLE.get(individual_group, {}):
                    style["image"] = GROUP_TO_STYLE[individual_group]["image"]
                    style["shape"] = "circularImage"
                else:
                    style["color"] = GROUP_TO_STYLE.get(individual_group, {}).get(
                        "color", "purple"
                    )
                    style["shape"] = GROUP_TO_STYLE.get(individual_group, {}).get(
                        "shape", "diamond"
                    )

                relations_individual = []
                if include_class_relation and entity_class:
                    relations_individual.append(
                        {
                            "label": "is a",
                            "to": entity_class,
                        }
                    )

                # Get all object properties pointing from this individual
                for pred, obj in full_graph.predicate_objects(individual_uri):
                    if isinstance(pred, URIRef) and isinstance(obj, URIRef):
                        # Check if obj is a NamedIndividual
                        obj_types = list(full_graph.objects(obj, RDF.type))
                        if OWL.NamedIndividual in obj_types:
                            # Get property label
                            property_label = get_rdfs_label(pred, graph, imported_graph)

                            # Get target individual ID
                            target_prefix = get_class_id_prefix(obj, graph)
                            target_short_name = get_short_name(obj)
                            target_id = f"{target_prefix}:{target_short_name}"

                            # Check for inverse relationship deduplication
                            forward_key = (individual_id, target_id)
                            inverse_key = (target_id, individual_id)
                            should_add = True

                            # Check if we've already seen this exact relationship
                            if forward_key in individual_relationships_seen:
                                should_add = False
                            elif inverse_key in individual_relationships_seen:
                                # Check if the properties are inverses
                                existing_prop_uri = individual_relationships_seen[
                                    inverse_key
                                ][1]
                                inverse_prop = get_inverse_property(pred, full_graph)
                                if inverse_prop and inverse_prop == existing_prop_uri:
                                    # This is an inverse relationship, skip it
                                    should_add = False
                                elif pred == get_inverse_property(
                                    existing_prop_uri, full_graph
                                ):
                                    # The existing property is the inverse of this one, skip it
                                    should_add = False

                            if should_add:
                                # Record this relationship
                                individual_relationships_seen[forward_key] = (
                                    property_label,
                                    pred,
                                )
                                relations_individual.append(
                                    {
                                        "label": property_label,
                                        "to": target_id,
                                    }
                                )

                return {
                    "id": individual_id,
                    "name": individual_name,
                    "type": "owl:NamedIndividual",
                    "subclassOf": str(subclassof_uri) if subclassof_uri else "",
                    "style": style,
                    "relations": relations_individual,
                }

            # Process classes for classes section (old format)
            for class_uri in classes:
                # Get class ID (prefix:short_name)
                prefix = get_class_id_prefix(class_uri, graph)
                short_name = get_short_name(class_uri)
                class_id = f"{prefix}:{short_name}"

                # Get name (rdfs:label)
                name = get_rdfs_label(class_uri, graph, imported_graph)
                if name:
                    name = name.capitalize()

                # Get definition (skos:definition)
                definitions = list(full_graph.objects(class_uri, SKOS.definition))
                definition = ""
                if definitions:
                    definition = str(definitions[0])
                    if "@" in definition:
                        definition = definition.split("@")[0]

                # Get examples (skos:example)
                examples_list = list(full_graph.objects(class_uri, SKOS.example))
                examples_str_list = [str(example) for example in examples_list]
                if examples_str_list:
                    examples = ", ".join(examples_str_list)
                else:
                    examples = ""

                # Get subClassOf
                subclassof_list = list(full_graph.objects(class_uri, RDFS.subClassOf))
                subclassof = ""
                subclassof_uri: Optional[URIRef] = None
                for subclassof_node in subclassof_list:
                    if isinstance(subclassof_node, URIRef):
                        subclassof_uri = subclassof_node
                        # Get class ID (prefix:short_name)
                        subclassof_prefix = get_class_id_prefix(
                            subclassof_uri, full_graph
                        )
                        subclassof_short_name = get_short_name(subclassof_uri)
                        subclassof = f"{subclassof_prefix}:{subclassof_short_name}"
                        break

                # Get group from subclass hierarchy
                group = get_group_from_class_hierarchy(class_uri, full_graph)
                if group is None:
                    group = "UNKNOWN"
                    logger.warning(
                        f"Could not determine group for class - URI: {class_uri}, Name: {name}"
                    )

                # Extract relationships from unique_relationships
                relations = []
                seen_relations = set()  # To avoid duplicates

                for source, target, property_uri in unique_relationships:
                    if source == class_uri and target in classes:
                        # Ensure property_uri is a URIRef
                        if not isinstance(property_uri, URIRef):
                            property_uri = URIRef(property_uri)

                        # Get property label (will check imported graph automatically)
                        property_label = get_rdfs_label(
                            property_uri, graph, imported_graph
                        )

                        # Get target class ID (prefix:short_name)
                        target_prefix = get_class_id_prefix(target, graph)
                        target_short_name = get_short_name(target)
                        target_id = f"{target_prefix}:{target_short_name}"

                        # Create relation key for deduplication
                        relation_key = (property_label, target_id)
                        if relation_key not in seen_relations:
                            seen_relations.add(relation_key)
                            relations.append({"label": property_label, "to": target_id})

                # Build class entry
                class_entry: dict = {
                    "id": class_id,
                    "name": name,
                    "description": definition,  # TODO: to be updated to definition
                    "examples": examples,
                    "class": str(subclassof_uri)
                    if subclassof_uri
                    else "",  # TODO: to be updated to subclassOf
                    "relations": relations,
                }

                if group:
                    class_entry["style"] = {"group": group}

                yaml_classes.append(class_entry)
                entity_class = class_id.split(":")[-1]

                if parameters.display_individuals_classes:
                    # Build entity entry (yellow square for classes)
                    entity_class_entry = {
                        "id": entity_class,
                        "name": name,
                        "type": "owl:Class",
                        "style": {
                            "group": "Class",
                            "color": "yellow",
                            "shape": "square",
                        },
                        "relations": [
                            {
                                "label": "is a",
                                "to": subclassof.split(":")[-1] if subclassof else "",
                            }
                        ]
                        if subclassof
                        else [],
                    }
                    yaml_entities.append(entity_class_entry)

                # Use existing NamedIndividuals if available, otherwise generate one as fallback
                individuals_for_class = named_individuals.get(class_uri, [])

                if total_individuals > 0:
                    # Case: Both classes and NamedIndividuals exist
                    # Use existing NamedIndividuals
                    for individual_uri in individuals_for_class:
                        # Get individual label
                        individual_labels = list(
                            full_graph.objects(individual_uri, RDFS.label)
                        )
                        individual_name = (
                            str(individual_labels[0])
                            if individual_labels
                            else get_short_name(individual_uri)
                        )
                        if "@" in individual_name:
                            individual_name = individual_name.split("@")[0]

                        # Get individual ID
                        individual_prefix = get_class_id_prefix(individual_uri, graph)
                        individual_short_name = get_short_name(individual_uri)
                        individual_id = f"{individual_prefix}:{individual_short_name}"

                        # Get group from class hierarchy
                        individual_group = get_group_from_class_hierarchy(
                            class_uri, full_graph
                        )
                        if individual_group is None:
                            individual_group = "UNKNOWN"

                        # Create individual entry with "is a" relation to class
                        entity_individual_entry = create_individual_entry(
                            individual_uri=individual_uri,
                            class_uri=class_uri,
                            individual_name=individual_name,
                            individual_id=individual_id,
                            individual_group=individual_group,
                            subclassof_uri=subclassof_uri,
                            entity_class=entity_class,
                            include_class_relation=True,
                        )
                        yaml_entities.append(entity_individual_entry)
                else:
                    # Case: Classes exist but no NamedIndividuals - create fallback entities
                    individual_group = get_group_from_class_hierarchy(
                        class_uri, full_graph
                    )
                    if individual_group is None:
                        individual_group = "UNKNOWN"

                    style = {
                        "group": individual_group,
                    }
                    if "image" in GROUP_TO_STYLE.get(individual_group, {}):
                        style["image"] = GROUP_TO_STYLE[individual_group]["image"]
                        style["shape"] = "circularImage"
                    else:
                        style["color"] = GROUP_TO_STYLE.get(individual_group, {}).get(
                            "color", "purple"
                        )
                        style["shape"] = GROUP_TO_STYLE.get(individual_group, {}).get(
                            "shape", "diamond"
                        )
                    entity_individual_entry = {
                        "id": entity_class + "_001",
                        "name": name + " 001",
                        "type": "owl:NamedIndividual",
                        "subclassOf": str(subclassof_uri) if subclassof_uri else "",
                        "style": style,
                        "relations": [
                            {
                                "label": "is a",
                                "to": entity_class,
                            }
                        ],
                    }
                    relations_individual = [
                        {
                            "label": "is a",
                            "to": entity_class,
                        }
                    ]
                    for relation in relations:
                        relation_label = relation["label"]
                        relation_to = relation["to"].split(":")[-1]
                        if str(relation_to) == str(entity_class):
                            continue

                        relations_individual.append(
                            {
                                "label": relation_label,
                                "to": relation_to + "_001",
                            }
                        )

                    if relations_individual:
                        entity_individual_entry["relations"] = relations_individual
                    yaml_entities.append(entity_individual_entry)

            # Case: Only NamedIndividuals (ABOX) - no classes in classes_set
            # Process NamedIndividuals that don't have corresponding classes
            if len(classes) == 0 and total_individuals > 0:
                logger.info(
                    "Processing ABOX-only ontology: NamedIndividuals without classes"
                )
                for class_uri, individual_uris in named_individuals.items():
                    # Get class information even though it's not in classes_set
                    # (might be from imported ontology)
                    subclassof_list = list(
                        full_graph.objects(class_uri, RDFS.subClassOf)
                    )
                    subclassof_uri = None
                    for subclassof_node in subclassof_list:
                        if isinstance(subclassof_node, URIRef):
                            subclassof_uri = subclassof_node
                            break

                    # Get group from class hierarchy
                    individual_group = get_group_from_class_hierarchy(
                        class_uri, full_graph
                    )
                    if individual_group is None:
                        individual_group = "UNKNOWN"

                    for individual_uri in individual_uris:
                        # Get individual label
                        individual_labels = list(
                            full_graph.objects(individual_uri, RDFS.label)
                        )
                        individual_name = (
                            str(individual_labels[0])
                            if individual_labels
                            else get_short_name(individual_uri)
                        )
                        if "@" in individual_name:
                            individual_name = individual_name.split("@")[0]

                        # Get individual ID
                        individual_prefix = get_class_id_prefix(individual_uri, graph)
                        individual_short_name = get_short_name(individual_uri)
                        individual_id = f"{individual_prefix}:{individual_short_name}"

                        # Create individual entry WITHOUT "is a" relation to class
                        # (since the class entity doesn't exist in yaml_entities)
                        entity_individual_entry = create_individual_entry(
                            individual_uri=individual_uri,
                            class_uri=class_uri,
                            individual_name=individual_name,
                            individual_id=individual_id,
                            individual_group=individual_group,
                            subclassof_uri=subclassof_uri,
                            entity_class=None,
                            include_class_relation=False,
                        )
                        yaml_entities.append(entity_individual_entry)

            # Create YAML structure with both classes and entities
            yaml_data = {"classes": yaml_classes, "entities": yaml_entities}

            # Generate output filename
            base_name = turtle_path_obj.stem
            yaml_path = output_dir_path / f"{base_name}.yaml"

            # Write YAML file
            logger.info(f"Saving YAML to: {yaml_path}")
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    yaml_data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )

            logger.info("YAML saved successfully!")

            if parameters.publish_to_workspace:
                self.__create_workspace_ontology_workflow.create_or_update_workspace_ontology(
                    CreateWorkspaceOntologyWorkflowParameters(
                        yaml_data=yaml_data,
                        label=parameters.ontology_name,
                        level="USE_CASE",
                        description=f"Ontology generated from: {turtle_path}",
                    )
                )
            return str(yaml_path)
        except Exception as e:
            error_msg = f"Error converting ontology to YAML: {str(e)}"
            logger.error(error_msg)
            raise

    def as_tools(self) -> list[BaseTool]:
        """
        Return a list of tools that can be used to interact with this workflow.

        Returns:
            list[StructuredTool]: List of tools
        """
        return [
            StructuredTool(
                name="convert_ontology_to_yaml_and_publish_to_workspace",
                description="Convert a Turtle ontology file to YAML format.",
                func=lambda **kwargs: self.convert_ontology_to_yaml(
                    ConvertOntologytoYamlWorkflowParameters(**kwargs)
                ),
                args_schema=ConvertOntologytoYamlWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None


if __name__ == "__main__":
    """
    Main entry point for the script.

    Convert Turtle ontology files to Pyvis network visualization and/or YAML format.

    Examples:
        # Convert to YAML only and publish to workspace
        uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology-engineer/workflows/ConvertOntologytoYamlWorkflow.py
    """
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.naas import ABIModule as NaasABIModule
    from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
        NaasIntegrationConfiguration,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.naas"])
    module = NaasABIModule.get_instance()
    workspace_id = module.configuration.workspace_id
    storage_name = module.configuration.storage_name
    create_workspace_ontology_config = CreateWorkspaceOntologyWorkflowConfiguration(
        naas_integration_config=NaasIntegrationConfiguration(
            api_key=engine.services.secret.get("NAAS_API_KEY"),
            workspace_id=workspace_id,
            storage_name=storage_name,
        )
    )
    turtle_path = "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/pipelines/insert_Florent_Ravenel.ttl"
    imported_ontologies = [
        "libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/ontologies/BFO7BucketsProcessOntology.ttl",
        "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/ontologies/imports/LinkedInOntology.ttl",
        "libs/naas-abi-marketplace/naas_abi_marketplace/applications/linkedin/ontologies/modules/ActOfConnectionsOnLinkedIn.ttl",
    ]
    ontology_name = "Florent Ravenel's Act of Connections on LinkedIn"
    display_individuals_classes = False

    # Create workflow configuration and instance
    configuration = ConvertOntologytoYamlWorkflowConfiguration(
        create_workspace_ontology_config=create_workspace_ontology_config
    )
    workflow = ConvertOntologytoYamlWorkflow(configuration)

    # Create parameters
    parameters = ConvertOntologytoYamlWorkflowParameters(
        turtle_path=turtle_path,
        imported_ontologies=imported_ontologies,
        publish_to_workspace=True,
        ontology_name=ontology_name,
        display_individuals_classes=display_individuals_classes,
    )

    # Execute workflow
    yaml_path = workflow.convert_ontology_to_yaml(parameters)
    print(f"YAML file generated at: {yaml_path}")

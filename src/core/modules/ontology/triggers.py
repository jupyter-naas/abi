# This file defines triggers for the opendata module
# Triggers allow the module to react automatically to changes in the ontology store
# Each trigger consists of:
#   1. A triple pattern (subject, predicate, object) where None acts as a wildcard
#   2. An event type (OntologyEvent.INSERT or OntologyEvent.DELETE)
#   3. A callback function to execute when the event occurs
#
# Example:
# from abi.services.ontology_store.OntologyStorePorts import OntologyEvent
# from rdflib import URIRef, Namespace
#
# ex = Namespace("http://example.org/")
#
# def handle_new_dataset(event_type, ontology_name, triple):
#     subject, predicate, obj = triple
#     # Process the new dataset here
#
# triggers = [
#     ((None, URIRef(ex + "hasOpenData"), None), OntologyEvent.INSERT, handle_new_dataset),
# ]

from src import services
from lib.abi.services.ontology_store.OntologyStorePorts import OntologyEvent
from rdflib import URIRef, Literal
from abi import logger

# Register organization logo update trigger
def push_ontology_to_naas_workspace():
    from src import secret
    from src.core.modules.common.integrations.NaasIntegration import NaasIntegrationConfiguration
    from src.core.modules.ontology.workflows.CreateClassOntologyYAML import CreateClassOntologyYAML, CreateClassOntologyYAMLConfiguration

    # Initialize ontology store
    ontology_store = services.ontology_store_service

    # Initialize integrations
    naas_integration_config = NaasIntegrationConfiguration(
        api_key=secret.get("NAAS_API_KEY")
    )

    # Initialize workflows
    create_class_ontology_yaml_config = CreateClassOntologyYAMLConfiguration(
        naas_integration_config=naas_integration_config,
        ontology_store=ontology_store
    )

    # Initialize workflow
    workflow = CreateClassOntologyYAML(create_class_ontology_yaml_config)

    # Subscribe to the trigger
    return ((None, None, None), OntologyEvent.INSERT, workflow.trigger)

triggers = [
    push_ontology_to_naas_workspace(),
]
# This file defines triggers for the opendata module
# Triggers allow the module to react automatically to changes in the ontology store
# Each trigger consists of:
#   1. A triple pattern (subject, predicate, object) where None acts as a wildcard
#   2. An event type (OntologyEvent.INSERT or OntologyEvent.DELETE)
#   3. A callback function to execute when the event occurs
#
# Example:
# from abi.services.triple_store.TripleStorePorts import OntologyEvent
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

from src import services, secret
from lib.abi.services.triple_store.TripleStorePorts import OntologyEvent
from rdflib import URIRef, Literal
from abi import logger

def create_class_ontology_yaml():
    from src.core.modules.naas.integrations.NaasIntegration import NaasIntegrationConfiguration
    from src.core.modules.ontology.workflows.ConvertOntologyGraphToYamlWorkflow import ConvertOntologyGraphToYamlConfiguration
    from src.core.modules.ontology.workflows.CreateClassOntologyYamlWorkflow import CreateClassOntologyYamlWorkflow, CreateClassOntologyYamlConfiguration
    
    # Get secrets
    naas_api_key = secret.get("NAAS_API_KEY")
    if naas_api_key is None:
        logger.error("NAAS_API_KEY is not set")
        return None
    
    # Configure Naas integration
    naas_integration_config = NaasIntegrationConfiguration(
        api_key=naas_api_key
    )

    # Configure ConvertOntologyGraphToYaml workflow
    convert_ontology_graph_config = ConvertOntologyGraphToYamlConfiguration(naas_integration_config)
    workflow = CreateClassOntologyYamlWorkflow(CreateClassOntologyYamlConfiguration(services.triple_store_service, convert_ontology_graph_config))

    # Subscribe to the trigger
    return ((None, None, None), OntologyEvent.INSERT, workflow.trigger, True)

def create_individual_ontology_yaml():
    from src.core.modules.naas.integrations.NaasIntegration import NaasIntegrationConfiguration
    from src.core.modules.ontology.workflows.ConvertOntologyGraphToYamlWorkflow import ConvertOntologyGraphToYamlConfiguration
    from src.core.modules.ontology.workflows.CreateIndividualOntologyYamlWorkflow import CreateIndividualOntologyYamlWorkflow, CreateIndividualOntologyYamlConfiguration
    
    # Get secrets
    naas_api_key = secret.get("NAAS_API_KEY")
    if naas_api_key is None:
        logger.error("NAAS_API_KEY is not set")
        return None
    
    # Configure Naas integration
    naas_integration_config = NaasIntegrationConfiguration(
        api_key=naas_api_key
    )

    # Configure ConvertOntologyGraphToYaml workflow
    convert_ontology_graph_config = ConvertOntologyGraphToYamlConfiguration(naas_integration_config)
    workflow = CreateIndividualOntologyYamlWorkflow(CreateIndividualOntologyYamlConfiguration(services.triple_store_service, convert_ontology_graph_config))

    # Subscribe to the trigger
    return ((None, None, None), OntologyEvent.INSERT, workflow.trigger, True)

triggers = [
    create_class_ontology_yaml(),
    create_individual_ontology_yaml(),
]
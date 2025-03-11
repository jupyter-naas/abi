from src import services
from lib.abi.services.ontology_store.OntologyStorePorts import OntologyEvent
from rdflib import URIRef, Literal
from abi import logger

# Register organization logo update trigger
def register_organization_logo_update_trigger():
    from src import secret, config
    from src.core.common.integrations.NaasIntegration import NaasIntegrationConfiguration
    from src.core.common.integrations.GoogleSearchIntegration import GoogleSearchIntegrationConfiguration
    from src.core.common.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
    from src.core.modules.opendata.workflows.LinkedInOrganizationsWorkflows import LinkedInOrganizationWorkflowsConfiguration
    from src.core.modules.opendata.pipelines.LinkedInGetOrganizationLogoPipeline import LinkedInGetOrganizationLogoPipeline, LinkedInGetOrganizationLogoPipelineConfiguration

    # Initialize ontology store
    ontology_store = services.ontology_store_service

    # Initialize integrations
    naas_integration_config = NaasIntegrationConfiguration(
        api_key=secret.get("NAAS_API_KEY")
    )
    google_search_integration_config = GoogleSearchIntegrationConfiguration()

    # Initialize workflows
    linkedin_organization_workflows_config = LinkedInOrganizationWorkflowsConfiguration(
        linkedin_integration_config=LinkedInIntegrationConfiguration(
            li_at=secret.get("li_at"),
            JSESSIONID=secret.get("JSESSIONID")
        ),
        google_search_integration_config=google_search_integration_config,
        naas_integration_config=naas_integration_config
    )

    # Initialize pipeline
    pipeline = LinkedInGetOrganizationLogoPipeline(LinkedInGetOrganizationLogoPipelineConfiguration(
        ontology_store=ontology_store,
        linkedin_organization_workflows_config=linkedin_organization_workflows_config,
    ))

    # Subscribe to the trigger
    services.ontology_store_service.subscribe((None, None, URIRef("https://www.commoncoreontologies.org/ont00000443")), OntologyEvent.INSERT, pipeline.trigger)

# Register organization size trigger
def register_organization_size_trigger():
    from src.core.modules.opendata.pipelines.OrganizationSizePipeline import OrganizationSizePipeline, OrganizationSizePipelineConfiguration

    # Initialize ontology store
    ontology_store = services.ontology_store_service

    # Initialize pipeline
    pipeline = OrganizationSizePipeline(OrganizationSizePipelineConfiguration(
        ontology_store=ontology_store
    ))

    # Subscribe to the trigger
    services.ontology_store_service.subscribe((None, URIRef("http://ontology.naas.ai/abi/number_of_employees"), None), OntologyEvent.INSERT, pipeline.trigger)
    
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

triggers = []

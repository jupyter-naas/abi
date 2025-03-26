from src.core.modules.ontology.workflows.CreateClassOntologyYAML import CreateClassOntologyYAML, CreateClassOntologyYAMLParameters, CreateClassOntologyYAMLConfiguration
from src.core.modules.common.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src import secret, config, services

workflow = CreateClassOntologyYAML(CreateClassOntologyYAMLConfiguration(
    ontology_store=services.ontology_store_service,
    naas_integration_config=NaasIntegrationConfiguration(
        api_key=secret.get("NAAS_API_KEY"),
    )
))

workflow.graph_to_yaml(CreateClassOntologyYAMLParameters(
    ontology_name="person_ont00001262",
    label="Person",
    description="Represents ontology Class of a person.",
    logo_url="https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png",
    level="USE_CASE"
))
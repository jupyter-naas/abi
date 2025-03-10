from src import secret, config, services
from src.core.integrations.PerplexityIntegration import PerplexityIntegrationConfiguration
from src.core.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.core.workflows.abi.CreateOntologyYAML import CreateOntologyYAMLConfiguration
from src.custom.pipelines.opendata.PerplexityOrganizationAnalysisPipeline import PerplexityOrganizationAnalysisPipeline, PerplexityOrganizationAnalysisPipelineConfiguration, PerplexityOrganizationAnalysisPipelineParameters
from src.custom.workflows.opendata.PerplexityGetOrganizationWorkflows import PerplexityOrganizationWorkflowsConfiguration

# Initialize ontology store
ontology_store = services.ontology_store_service

# Initialize integrations
naas_integration_config = NaasIntegrationConfiguration(
    api_key=secret.get("NAAS_API_KEY")
)
perplexity_organization_workflows_config = PerplexityOrganizationWorkflowsConfiguration(
    perplexity_integration_config=PerplexityIntegrationConfiguration(api_key=secret.get("PERPLEXITY_API_KEY")),
)
create_ontology_yaml_config = CreateOntologyYAMLConfiguration(
    naas_integration_config=naas_integration_config,
    ontology_store=ontology_store
)

# Initialize pipeline
pipeline = PerplexityOrganizationAnalysisPipeline(PerplexityOrganizationAnalysisPipelineConfiguration(
    ontology_store=ontology_store,
    naas_integration_config=naas_integration_config,
    perplexity_organization_workflows_config=perplexity_organization_workflows_config,
    create_ontology_yaml_config=create_ontology_yaml_config,
))

organization_name = "Softbank"
website = "https://www.softbank.jp/"

pipeline.run(PerplexityOrganizationAnalysisPipelineParameters(
    organization_name=organization_name,
    website=website,
    use_cache=True
))
from src import secret, config, services
from src.core.modules.common.integrations.PerplexityIntegration import PerplexityIntegrationConfiguration
from src.core.modules.common.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.core.modules.common.workflows.abi.CreateOntologyYAML import CreateOntologyYAMLConfiguration
from src.core.modules.opendata.pipelines.PerplexityOrganizationAnalysisPipeline import PerplexityOrganizationAnalysisPipeline, PerplexityOrganizationAnalysisPipelineConfiguration, PerplexityOrganizationAnalysisPipelineParameters
from src.core.modules.opendata.workflows.PerplexityGetOrganizationWorkflows import PerplexityOrganizationWorkflowsConfiguration

# Initialize ontology store
triple_store = services.triple_store_service

# Initialize integrations
naas_integration_config = NaasIntegrationConfiguration(
    api_key=secret.get("NAAS_API_KEY")
)
perplexity_organization_workflows_config = PerplexityOrganizationWorkflowsConfiguration(
    perplexity_integration_config=PerplexityIntegrationConfiguration(api_key=secret.get("PERPLEXITY_API_KEY")),
)
create_ontology_yaml_config = CreateOntologyYAMLConfiguration(
    naas_integration_config=naas_integration_config,
    triple_store=triple_store
)

# Initialize pipeline
pipeline = PerplexityOrganizationAnalysisPipeline(PerplexityOrganizationAnalysisPipelineConfiguration(
    triple_store=triple_store,
    naas_integration_config=naas_integration_config,
    perplexity_organization_workflows_config=perplexity_organization_workflows_config,
    create_ontology_yaml_config=create_ontology_yaml_config,
))

organization_name = "Michelin"
website = "https://www.michelin.com/"

pipeline.run(PerplexityOrganizationAnalysisPipelineParameters(
    organization_name=organization_name,
    website=website,
    use_cache=True
))
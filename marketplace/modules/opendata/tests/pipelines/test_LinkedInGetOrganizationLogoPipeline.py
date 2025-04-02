from src import secret, config, services
from src.core.modules.common.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.core.modules.common.integrations.GoogleSearchIntegration import GoogleSearchIntegrationConfiguration
from src.core.modules.common.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
from src.core.modules.opendata.workflows.LinkedInOrganizationsWorkflows import LinkedInOrganizationWorkflowsConfiguration
from src.core.modules.opendata.pipelines.LinkedInGetOrganizationLogoPipeline import LinkedInGetOrganizationLogoPipeline, LinkedInGetOrganizationLogoPipelineConfiguration, LinkedInGetOrganizationLogoPipelineParameters

# Initialize ontology store
triple_store = services.triple_store_service

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
    triple_store=triple_store,
    linkedin_organization_workflows_config=linkedin_organization_workflows_config,
))

pipeline.run(LinkedInGetOrganizationLogoPipelineParameters(
    ontology_name="shopify",
    organization_uri="http://ontology.naas.ai/abi/ont00000443#shopify"
))
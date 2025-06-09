from src.core.modules.naas.pipelines.ImageURLtoAssetPipeline import ImageURLtoAssetPipeline, ImageURLtoAssetPipelineParameters, ImageURLtoAssetPipelineConfiguration
from src.core.modules.naas.integrations.NaasIntegration import NaasIntegrationConfiguration
from src import secret, services
from abi import logger

# Configuration
api_key = secret.get("NAAS_API_KEY")
naas_integration_config = NaasIntegrationConfiguration(api_key=api_key)
pipeline_config = ImageURLtoAssetPipelineConfiguration(naas_integration_config=naas_integration_config, triple_store=services.triple_store_service)
pipeline = ImageURLtoAssetPipeline(pipeline_config)

# Parameters
image_url = "https://media.licdn.com/dms/image/v2/C560BAQEOzG0TtTclXw/company-logo_200_200/company-logo_200_200/0/1630669062399?e=1755129600&v=beta&t=bgJLEuDIm89RlXA_QCd7tBVzZCQufZiDY5_SzZJABDw"
subject_uri = "http://ontology.naas.ai/abi/4d4e6bc4-b396-4d26-b42b-3d257cde1738"
predicate_uri = "http://ontology.naas.ai/abi/logo"
parameters = ImageURLtoAssetPipelineParameters(image_url=image_url, subject_uri=subject_uri, predicate_uri=predicate_uri)

# Execute
result = pipeline.run(parameters)
print(result)
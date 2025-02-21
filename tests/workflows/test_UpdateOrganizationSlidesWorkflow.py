from src.core.workflows.powerpoint.UpdateSlidesWorkflow import UpdateSlidesWorkflow, UpdateSlidesWorkflowConfiguration, UpdateSlidesWorkflowParameters
from abi import logger
from src import secret
from src.core.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.core.integrations.OpenAIIntegration import OpenAIIntegrationConfiguration
from src.core.integrations.PowerPointIntegration import PowerPointIntegrationConfiguration

# Initialize naas integration
naas_integration_config = NaasIntegrationConfiguration(
    api_key=secret.get("NAAS_API_KEY")
)

# Initialize openai integration
openai_integration_config = OpenAIIntegrationConfiguration(
    api_key=secret.get("OPENAI_API_KEY")
)

# Initialize powerpoint integration
powerpoint_integration_config = PowerPointIntegrationConfiguration()

# Run workflow
configuration = UpdateSlidesWorkflowConfiguration(
    powerpoint_integration_config=powerpoint_integration_config,
    openai_integration_config=openai_integration_config,
    naas_integration_config=naas_integration_config,
)
workflow = UpdateSlidesWorkflow(configuration)
text = """
NaasAI is a pioneering AI company specializing in natural language processing and machine learning solutions. 
Our core offerings include AI model development, data analytics, and automated workflow systems. We have extensive expertise in language models, computer vision, and enterprise AI applications.

Our technology stack is built on cutting-edge AI/ML frameworks, cloud infrastructure, and proprietary algorithms. We leverage state-of-the-art language models and neural networks to deliver intelligent automation solutions. Our team consists of AI researchers, data scientists, and software engineers who collaborate to solve complex AI challenges.

In the market, we serve enterprise clients across technology, finance, healthcare and other industries. 
Our global reach includes partnerships with leading cloud providers and technology companies. 
We differentiate ourselves from competitors through our specialized AI expertise and custom solutions.

Our value proposition centers on AI innovation and practical business applications. Key differentiators include:
- Advanced AI/ML capabilities and research
- Custom model development and training
- Scalable cloud-native architecture
- End-to-end AI solution delivery
- Industry-specific AI applications
"""
use_cache = True
output = workflow.update_slides(UpdateSlidesWorkflowParameters(text=text, use_cache=use_cache))
logger.info(output)
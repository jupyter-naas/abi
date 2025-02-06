from src.integrations.PowerPointIntegration import PowerPointIntegration, PowerPointIntegrationConfiguration
from abi import logger

# Initialize configuration
template_path = ""
configuration = PowerPointIntegrationConfiguration(template_path=template_path)

# Initialize integration
ppt = PowerPointIntegration(configuration)

# Create a new presentation
slides = ppt.list_slides()
logger.info(slides)
from src.integrations.PowerPointIntegration import PowerPointIntegration, PowerPointIntegrationConfiguration

# Initialize configuration
template_path = ""
configuration = PowerPointIntegrationConfiguration(template_path=template_path)

# Initialize integration
ppt = PowerPointIntegration(configuration)

# Create a new presentation
slides = ppt.list_slides()
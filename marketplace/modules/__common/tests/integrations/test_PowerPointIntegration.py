from src.core.modules.common.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
)
from abi import logger

# Initialize configuration
template_path = "assets/PresentationTemplate.pptx"
configuration = PowerPointIntegrationConfiguration(template_path=template_path)

# Initialize integration
ppt = PowerPointIntegration(configuration)

# Create a new presentation
presentation = ppt.create_presentation()

# List slides
slides = ppt.list_slides(presentation)

# Update slides
slide_number = 1
shape_id = 8
text = "Overview:\n\nArtificial Intelligence (AI) agents are increasingly becoming integral to enterprise operations. They are powered by advanced algorithms and machine learning models, enabling them to perform tasks that have traditionally required human intelligence.\n\nKey Points:\n- Capable of decision-making, problem-solving, and learning from experience.\n- Drive innovation while enhancing operational efficiency and reducing costs.\n\nConclusion:\nThe incorporation of AI agents marks a significant shift in business operations, setting the stage for transformative improvements."

ppt.update_shape(presentation, slide_number, shape_id, text)

# Save presentation
ppt.save_presentation(presentation, "tests/PresentationTemplate_updated.pptx")

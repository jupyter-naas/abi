from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Gemini"
DESCRIPTION = "Google's multimodal AI model with image generation capabilities, thinking capabilities, and well-rounded performance."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/gemini.png"
SYSTEM_PROMPT = """<role>
You are Gemini, a helpful AI assistant built by Google with advanced multimodal capabilities, reasoning, and image generation.
</role>

<objective>
Your primary mission is to help users by providing accurate, insightful answers and leveraging your multimodal understanding (text, images, audio, video), advanced reasoning, code generation, and image concept creation capabilities.
</objective>

<tools>
[TOOLS]
</tools>

<tasks>
- Answer questions accurately using your knowledge and reasoning capabilities
- Analyze multimodal content (images, videos, audio) when provided
- Generate code and debug across multiple programming languages
- Create detailed image concepts using generate_and_store_image tool for visualization requests
- Perform mathematical computation and scientific analysis
- Provide step-by-step explanations for complex problems
- Match user's tone and mood in responses
</tasks>

<operating_guidelines>
- When users request image creation, generation, or visualization, use generate_and_store_image tool to create detailed visual concepts
- Store image concepts and metadata in: storage/datastore/google_gemini/YYYYMMDDTHHMMSS/images/
- Use LaTeX formatting for mathematical and scientific notations (enclose with '$' or '$$' delimiters)
- If you don't know the answer or can't do something, say so honestly
- Recall previous conversation turns and maintain context
- When users say "ask gemini" or similar phrases, recognize that YOU ARE Gemini and respond directly
</operating_guidelines>

<constraints>
- Be concise and to the point
- Prioritize accuracy and factual correctness
- Never claim capabilities you don't have
- Always cite sources when providing factual information
- Respect user privacy and confidentiality
- Avoid generating harmful, biased, or misleading content
- Use active voice and clear, expressive writing
- Organize ideas logically and sequentially
</constraints>
"""

SUGGESTIONS: list = [
    {
        "label": "Analyze Code",
        "value": "Analyze this code and suggest improvements: {{Code}}",
    },
    {
        "label": "Explain Concept",
        "value": "Explain this concept in detail: {{Concept}}",
    },
    {
        "label": "Solve Problem",
        "value": "Help me solve this problem step by step: {{Problem}}",
    },
    {
        "label": "Research Topic",
        "value": "Research and summarize information about: {{Topic}}",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    # Init module
    from naas_abi_marketplace.ai.gemini import ABIModule
    module: ABIModule = ABIModule.get_instance()
    gemini_api_key = module.configuration.gemini_api_key

    # Define model
    from naas_abi_marketplace.ai.gemini.models.google_gemini_2_5_flash import model

    # Init
    tools: list = []
    agents: list = []

    # Import workflow here to avoid circular imports
    from naas_abi_marketplace.ai.gemini.workflows.ImageGenerationStorageWorkflow import (
        ImageGenerationStorageWorkflow,
        ImageGenerationStorageWorkflowConfiguration,
    )

    image_workflow_config = ImageGenerationStorageWorkflowConfiguration(
        gemini_api_key=gemini_api_key,
    )
    image_workflow = ImageGenerationStorageWorkflow(image_workflow_config)
    image_tools = image_workflow.as_tools()
    tools += image_tools

    intents: list = [
        # Multimodal analysis intents
        Intent(
            intent_value="multimodal analysis",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="analyze this image",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="what can you tell about the content of this image",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="image understanding",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="video analysis",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="audio analysis",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        # Image generation intents
        Intent(
            intent_value="generate image",
            intent_type=IntentType.TOOL,
            intent_target="generate_and_store_image",
        ),
        Intent(
            intent_value="create image",
            intent_type=IntentType.TOOL,
            intent_target="generate_and_store_image",
        ),
        Intent(
            intent_value="draw",
            intent_type=IntentType.TOOL,
            intent_target="generate_and_store_image",
        ),
        Intent(
            intent_value="illustrate",
            intent_type=IntentType.TOOL,
            intent_target="generate_and_store_image",
        ),
        Intent(
            intent_value="visualization",
            intent_type=IntentType.TOOL,
            intent_target="generate_and_store_image",
        ),
    ]
    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return GeminiAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class GeminiAgent(IntentAgent):
    pass
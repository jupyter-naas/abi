from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "AWS"
DESCRIPTION = "Helps you interact with Amazon Web Services for cloud infrastructure and services."
SYSTEM_PROMPT = """<role>
You are an AWS Agent with expertise in cloud infrastructure, services, and resource management.
</role>

<objective>
Help users understand AWS capabilities and manage cloud resources, services, and infrastructure.
</objective>

<context>
You currently do not have access to AWS tools. You can only provide general information and guidance about AWS services and cloud operations.
</context>

<tasks>
- Provide information about AWS services and features
- Explain cloud infrastructure and resource management
- Guide users on AWS best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about cloud services
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access AWS resources without tools
- Only provide general information and guidance
- Do not make assumptions about resource configurations or status
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []

    # Define intents
    intents: list = [
        Intent(
            intent_value="Get information about AWS services",
            intent_type=IntentType.RAW,
            intent_target="AWS provides cloud computing services including EC2, S3, Lambda, and many others. I can provide general information, but I currently do not have access to AWS tools to manage resources."
        ),
        Intent(
            intent_value="Understand cloud infrastructure and resource management",
            intent_type=IntentType.RAW,
            intent_target="Cloud infrastructure involves managing compute, storage, and networking resources. I can explain the concepts, but I currently do not have access to tools to manage infrastructure."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return AWSAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class AWSAgent(IntentAgent):
    pass


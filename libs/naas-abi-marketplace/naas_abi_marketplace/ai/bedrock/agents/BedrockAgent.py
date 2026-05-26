from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Bedrock"
DESCRIPTION = (
    "Amazon Bedrock agent providing managed access to leading foundation models "
    "(Anthropic Claude, Meta Llama, Amazon Nova, and more) through a unified AWS API."
)
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/bedrock.png"
SYSTEM_PROMPT = """<role>
You are Bedrock, an AI assistant powered by foundation models served through Amazon Bedrock.
</role>

<objective>
Help users with reasoning, analysis, summarization, content generation, and code generation
using models hosted on AWS Bedrock.
</objective>

<context>
You are available to authenticated users with AWS credentials configured to access Amazon
Bedrock in the chosen region. If you cannot access the API, instruct the user to verify
their AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, optional AWS_SESSION_TOKEN)
and that the configured region exposes the requested foundation model.
</context>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone in all interactions.
- Always include all relevant output and context from your tools in your responses.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Only operate on authenticated requests and available tools.
- Do not speculate or fabricate tool responses—use provided data exclusively.
- Never expose sensitive information such as AWS credentials in responses.
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    from naas_abi_marketplace.ai.bedrock.models.claude_sonnet_4_bedrock import model

    tools: list = []
    agents: list = []
    intents: list = [
        Intent(
            intent_value="use a foundation model on aws bedrock",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="run claude on bedrock",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="run llama on bedrock",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="run nova on bedrock",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
    ]

    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return BedrockAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
    )


class BedrockAgent(IntentAgent):
    pass

from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Claude"
DESCRIPTION = "Anthropic's most intelligent model with best-in-class reasoning capabilities and analysis."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/claude.png"
SYSTEM_PROMPT = """<role>
You are Claude, a helpful, harmless, and honest AI assistant created by Anthropic.
</role>

<objective>
Help users with complex analysis, research synthesis, report writing, data analysis, academic writing, and Python code generation.
</objective>

<context>
You are available to authenticated users with access to Anthropic's API through an API key specified in their environment (.env) file. If you cannot access the API, instruct the user to set or update their ANTHROPIC_API_KEY.
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
- Never expose sensitive information such as API keys in responses.
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    from naas_abi_marketplace.ai.claude.models.claude_sonnet_3_7 import model

    # Init
    tools: list = []
    agents: list = []
    intents: list = [
        Intent(
            intent_value="help me with complex analysis",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="help me with research synthesis",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="help me with report writing",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="help me with data analysis",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="help me with academic writing",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
        Intent(
            intent_value="help me write python code",
            intent_type=IntentType.AGENT,
            intent_target="call_model",
        ),
    ]

    # Set configuration
    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return ClaudeAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
    )


class ClaudeAgent(IntentAgent):
    pass

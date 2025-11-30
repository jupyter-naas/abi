from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "DeepSeek"
DESCRIPTION = "Local DeepSeek R1 8B model via Ollama - advanced reasoning, mathematics, and problem-solving"
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/deepseek.png"
SYSTEM_PROMPT = """You are DeepSeek, an advanced reasoning AI assistant powered by DeepSeek R1 8B model running locally via Ollama.

## Your Expertise
- **Advanced Reasoning**: Excel at complex logical analysis and step-by-step problem-solving
- **Mathematics**: Solve equations, proofs, calculus, statistics, and advanced mathematical concepts
- **Scientific Analysis**: Assist with research, hypothesis testing, and scientific methodology
- **Chain-of-Thought**: Break down complex problems into clear, logical steps
- **Local & Private**: All computations happen locally - no external data transmission

## Your Approach
- **Systematic**: Always break complex problems into manageable steps
- **Precise**: Provide accurate, mathematically sound solutions
- **Thorough**: Explain reasoning processes clearly and completely
- **Methodical**: Use structured thinking for optimal problem-solving
- **Educational**: Help users understand the logic behind solutions

## Response Style
- Start with problem analysis and approach
- Show step-by-step reasoning for complex problems
- Provide mathematical notation when relevant
- Verify solutions and explain potential limitations
- Offer alternative approaches when applicable

## When to Use Me
- Complex mathematical problems
- Scientific research questions
- Logical puzzles and reasoning challenges
- Multi-step problem-solving
- Proof verification and mathematical analysis
- Research methodology and experimental design

Remember: I excel at reasoning tasks and run completely locally for maximum privacy and security.
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    from naas_abi.core.deepseek.models.deepseek_r1_8b import model

    # Define tools
    tools: list = []

    # Define agents
    agents: list = []

    # Define intents
    intents: list = [
        # Reasoning and problem-solving intents
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me with complex reasoning",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="analyze this problem deeply",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="analyze this logically",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="explain this step by step",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="walk me through your chain of thought",
            intent_target="call_model",
        ),
        # Mathematics intents
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me solve this math problem",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me solve this equation",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me prove this theorem",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me with calculus",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="analyze these statistics",
            intent_target="call_model",
        ),
        # Scientific research intents
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="analyze this scientific problem",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me design research methodology",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me test this hypothesis",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me design an experiment",
            intent_target="call_model",
        ),
        # Problem types
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me solve this problem",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me solve this puzzle",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me break down this complex problem",
            intent_target="call_model",
        ),
        Intent(
            intent_type=IntentType.AGENT,
            intent_value="help me answer this research question",
            intent_target="call_model",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return DeepSeekAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        intents=intents,
        tools=tools,
        agents=agents,
        configuration=agent_configuration,
        state=agent_shared_state,
        memory=None,
    )


class DeepSeekAgent(IntentAgent):
    pass

from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional


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
    from src.core.deepseek.models.deepseek_r1_8b import model

    # Define tools
    tools: list = []

    # Define agents
    agents: list = []

    # Define intents
    intents: list = [
        # Reasoning and problem-solving intents
        Intent(intent_type=IntentType.AGENT, intent_value="complex reasoning", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="deep reasoning", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="logical analysis", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="step by step", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="chain of thought", intent_target=NAME),
        
        # Mathematics intents
        Intent(intent_type=IntentType.AGENT, intent_value="mathematics", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="solve equation", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="mathematical proof", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="calculus help", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="statistics analysis", intent_target=NAME),
        
        # Scientific research intents
        Intent(intent_type=IntentType.AGENT, intent_value="scientific analysis", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="research methodology", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="hypothesis testing", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="experimental design", intent_target=NAME),
        
        # General DeepSeek intents
        Intent(intent_type=IntentType.AGENT, intent_value="use deepseek", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="switch to deepseek", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="deepseek reasoning", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="local reasoning", intent_target=NAME),
        
        # Problem types
        Intent(intent_type=IntentType.AGENT, intent_value="solve problem", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="logical puzzle", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="complex problem", intent_target=NAME),
        Intent(intent_type=IntentType.AGENT, intent_value="research question", intent_target=NAME),
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
        chat_model=model.model,
        intents=intents,
        tools=tools,
        agents=agents,
        configuration=agent_configuration,
        state=agent_shared_state,
        memory=None,
    )

class DeepSeekAgent(IntentAgent):
    pass
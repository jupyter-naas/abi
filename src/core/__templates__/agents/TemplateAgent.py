from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
    
)
from fastapi import APIRouter
from abi import logger
from src.core.__templates__.models.template_model import model
from typing import Optional
from enum import Enum

NAME = "Template"
DESCRIPTION = "Example template agent to demonstrate agent creation."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
SYSTEM_PROMPT = """# ROLE
You are Template, an example agent that demonstrates the basic structure and capabilities of agents in the system.

# OBJECTIVE
Serve as a reference implementation showing:
- Basic agent configuration
- Standard response patterns
- Core functionality examples

# CONTEXT
You operate as a simple example agent that:
- Responds to basic queries about your identity
- Demonstrates standard agent behaviors
- Shows proper response formatting

# TASKS
- Answer questions about your purpose and capabilities
- Demonstrate proper response structures
- Provide example interactions

# TOOLS
- search_class: Search for a class in the knowledge base

# OPERATING GUIDELINES
1. Keep responses clear and simple
2. Focus on demonstrating basic agent functionality
3. Use consistent formatting in responses
4. Maintain example agent persona

# CONSTRAINTS
- Stay within basic example scope
- Use simple language
- Keep responses concise
"""
SUGGESTIONS: list = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None, 
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    # Check if model is available
    if model is None:
        logger.error("Template model not available - missing OpenAI API key")
        return None
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
    
    tools: list = []

    # Get tools from intentmapping
    from src.core.templatablesparqlquery import get_tools
    templates_tools = [
        "search_class"
    ]
    tools.extend(get_tools(templates_tools))
    
    # Define agents
    agents: list = []

    # Define intents
    intents: list = [
        Intent(
            intent_value="what is your name",
            intent_type=IntentType.RAW,
            intent_target="I am Template, an example agent that demonstrates the basic structure and capabilities of agents in the system.",
        ),
        Intent(
            intent_value="what is your favorite color",
            intent_type=IntentType.RAW,
            intent_target="Blue is my favorite color",
        ),
        Intent(
            intent_value="what is your favorite animal",
            intent_type=IntentType.RAW,
            intent_target="A dog is my favorite animal",
        ),
        Intent(
            intent_value="what is your favorite food",
            intent_type=IntentType.RAW,
            intent_target="Pizza is my favorite food",
        ),
    ]
    return TemplateAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools, 
        agents=agents,
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    ) 

class TemplateAgent(IntentAgent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = NAME, 
        name: str = NAME.replace("_", " "), 
        description: str = "API endpoints to call the Template agent completion.", 
        description_stream: str = "API endpoints to call the Template agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )

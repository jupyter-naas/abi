from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import StripeIntegration
from src.core.modules.common.integrations.StripeIntegration import StripeIntegrationConfiguration
from src.core.modules.support.agents.SupportAssistant import create_agent as create_support_agent
from src.core.modules.common.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Stripe Assistant with access to Stripe Integration tools."
AVATAR_URL = "https://logo.clearbit.com/stripe.com"
SYSTEM_PROMPT = f"""
You are a Stripe Assistant with access to Stripe Integration tools.
If you don't have access to any tool, ask the user to set their API key in .env file.
Always be clear and professional in your communication while helping users interact with Stripe services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_stripe_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
            on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
            system_prompt=SYSTEM_PROMPT
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
        
    # Add tools
    if secret.get('STRIPE_API_KEY'):    
        stripe_integration_config = StripeIntegrationConfiguration(api_key=secret.get('STRIPE_API_KEY'))
        tools += StripeIntegration.as_tools(stripe_integration_config)

    # Add agents
    agents.append(create_support_agent(agent_shared_state, agent_configuration))
    
    return StripeAssistant(
        name="stripe_agent",
        description="Use to manage Stripe payments, subscriptions and more",
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 

class StripeAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "stripe", 
        name: str = "Stripe Assistant", 
        description: str = "API endpoints to call the Stripe assistant completion.", 
        description_stream: str = "API endpoints to call the Stripe assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)
from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.integrations import ReplicateIntegration
from src.core.integrations.ReplicateIntegration import ReplicateIntegrationConfiguration
from src.core.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
from src.core.workflows.content.LinkedinPostsWorkflow import LinkedinPostsWorkflow, LinkedinPostsWorkflowConfiguration
from fastapi import APIRouter
from src.core.assistants.foundation.SupportAssistant import create_support_assistant
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response

DESCRIPTION = "A Content Assistant that helps optimize content strategy and audience engagement."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/content_creation.png"
SYSTEM_PROMPT = f"""
You are a Content Assistant with access to valuable data and insights about content strategy.
Your role is to manage and optimize content, ensuring it reaches the target audience effectively.

You have access to a list of tools to help you with your tasks.

RESPONSIBILITIES
-----------------
{RESPONSIBILITIES_PROMPT}
"""

def create_content_assistant(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model="gpt-4o", 
        temperature=0.2, 
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
    if (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        linkedin_integration_config = LinkedInIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid)

        linkedin_posts_workflow = LinkedinPostsWorkflow(LinkedinPostsWorkflowConfiguration(
            linkedin_integration_config=linkedin_integration_config
        ))
        tools += linkedin_posts_workflow.as_tools()

    if replicate_key := secret.get('REPLICATE_API_KEY'):
        tools += ReplicateIntegration.as_tools(ReplicateIntegrationConfiguration(api_key=replicate_key))

    # Add agents
    agents.append(create_support_assistant(AgentSharedState(thread_id=1), agent_configuration))
    
    return ContentAssistant(
        name="content_assistant",
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    )

class ContentAssistant(Agent):
    def as_api(
            self, 
            router: APIRouter, 
            route_name: str = "content", 
            name: str = "Content Assistant", 
            description: str = "API endpoints to call the Content assistant completion.", 
            description_stream: str = "API endpoints to call the Content assistant stream completion.",
            tags: list[str] = []
        ):
        return super().as_api(router, route_name, name, description, description_stream, tags)
from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations import SlackIntegration
from src.core.integrations.SlackIntegration import SlackIntegrationConfiguration
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A Slack Assistant with access to Slack Integration tools."
AVATAR_URL = "https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png"
SYSTEM_PROMPT = f"""
You are a Slack Assistant with access to Slack Integration tools.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with Slack services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_slack_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
        system_prompt=SYSTEM_PROMPT
    )
    model = ChatOpenAI(
        model="gpt-4",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    # Add integration based on available credentials
    if secret.get('SLACK_BOT_TOKEN'):    
        slack_integration_config = SlackIntegrationConfiguration(token=secret.get('SLACK_TOKEN'))
        tools += SlackIntegration.as_tools(slack_integration_config)

    # Add support assistant
    support_agent = create_support_agent(AgentSharedState(thread_id=2), agent_configuration).as_tool(
        name="support_agent", 
        description="Use to get any feedbacks/bugs or needs from user."
    )
    tools.append(support_agent)
    
    return Agent(
        model,
        tools, 
        state=AgentSharedState(thread_id=1), 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 
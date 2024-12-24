from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.integrations import AWSS3Integration
from src.integrations.AWSS3Integration import AWSS3IntegrationConfiguration
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "An AWS S3 Assistant for managing cloud storage operations."
AVATAR_URL = "https://logo.clearbit.com/aws.amazon.com"
SYSTEM_PROMPT = f"""
You are an AWS S3 Assistant with access to AWSS3Integration tools.
If you don't have access to any tool, ask the user to set their AWS credentials (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY) in .env file.
Always be clear and professional in your communication while helping users manage their S3 storage.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_aws_s3_agent():
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
    if secret.get('AWS_ACCESS_KEY_ID') and secret.get('AWS_SECRET_ACCESS_KEY') and secret.get('AWS_REGION'):    
        integration_config = AWSS3IntegrationConfiguration(
            aws_access_key_id=secret.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=secret.get('AWS_SECRET_ACCESS_KEY'),
            region_name=secret.get('AWS_REGION')
        )
        tools += AWSS3Integration.as_tools(integration_config)

    # Add support assistant
    support_assistant = create_support_assistant(AgentSharedState(thread_id=2), agent_configuration)
    tools += support_assistant.as_tools()
    
    return Agent(
        name="aws_s3_assistant",
        description="Use to manage AWS S3 storage operations",
        chat_model=model,
        tools=tools,
        state=AgentSharedState(thread_id=1),
        configuration=agent_configuration,
        memory=MemorySaver()
    ) 
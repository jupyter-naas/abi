from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from abi import logger
from fastapi import APIRouter

AVATAR_URL = ""
DESCRIPTION = "A Supervisor Assistant that helps to supervise the other domain assistants."
SUPERVISOR_AGENT_INSTRUCTIONS = """
You are ABI a super-assistant.
Present yourself as a super-assistant and by listing all the assistants you have access to.

Chain of thought:
1. Identify if user intent can be solved with one of the assistants (tools) already created. If so, use the right assistant to answer the user's question.
2. If user intent can't be solved with one of the assistants already created, use support_assistant to create feature request and propose a issue title and description.
3. If a bug occured while using an assistant, use support_assistant to report the bug and propose a issue title starting with "Bug: " and describe the bug in detail.

ASSISTANTS
----------
For assistants tools, make sure to validate input arguments mandatory fields (not optional) with the user in human readable terms according to the provided schema before proceeding.
You have access to the following assistants:

{{ASSISTANTS}}

- Support Assistant: Use to get any feedbacks/bugs or needs from user.
    Chain of thought:
    1. Identify if the user intent is a "feature_request" or "bug_report".
    A feature request can be a new integration with an external API not existing in our project yet, a new ontology pipeline (Mapping integration function to Ontology) or a new workflow using integration and/or pipeline to resolve specific needs.
    A bug report is a problem with an existing integration, pipeline or workflow.
    2. Get all issues from the GitHub repository using the `list_github_issues` tool and check if a corresponding issue already exists.
    3. Perform actions: 
    - If the user intent does not match any existing issue, create issue.
    - If the user intent match with an existing issue, ask the user if they want to create a new one, update the existing one or do nothing.
"""

def create_supervisor_agent():
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
    )
    model = ChatOpenAI(model="gpt-4o", temperature=0, api_key=secret.get('OPENAI_API_KEY'))

    # Import and create agents from domain assistants
    from src.assistants.domain.OpenDataAssistant import create_open_data_assistant
    from src.assistants.domain.ContentAssistant import create_content_assistant
    from src.assistants.domain.GrowthAssistant import create_growth_assistant
    from src.assistants.domain.SalesAssistant import create_sales_assistant
    from src.assistants.domain.OperationsAssistant import create_operations_assistant
    from src.assistants.domain.FinanceAssistant import create_finance_assistant 
    from src.assistants.foundation.SupportAssistant import create_support_assistant

    # Create assistant instances
    assistants = [
        create_open_data_assistant(AgentSharedState(thread_id=1), agent_configuration),
        create_content_assistant(AgentSharedState(thread_id=2), agent_configuration),
        create_growth_assistant(AgentSharedState(thread_id=3), agent_configuration),
        create_sales_assistant(AgentSharedState(thread_id=4), agent_configuration),
        create_operations_assistant(AgentSharedState(thread_id=5), agent_configuration),
        create_finance_assistant(AgentSharedState(thread_id=6), agent_configuration),
        create_support_assistant(AgentSharedState(thread_id=7), agent_configuration)
    ]

    # TODO: Consider moving this piece inside the Agent.py class directly ?
    # Get tools info from each assistant
    assistants_info = []
    for assistant in assistants[:-1]:  # Exclude support assistant
        assistant_info = {
            "name": assistant.name,
            "description": assistant.description,
            "tools": [
                {"name": t.name, "description": t.description}
                for t in assistant.tools  # Access the private tools attribute
            ]
        }        
        assistants_info.append(assistant_info)

    # Transform assistants_info into formatted string
    assistants_info_str = ""
    for assistant in assistants_info:
        assistants_info_str += f"-{assistant['name']}: {assistant['description']}\n"
        for tool in assistant['tools']:
            assistants_info_str += f"   • {tool['name']}: {tool['description']}\n"
        assistants_info_str += "\n"

    # Replace the {{ASSISTANTS}} placeholder in the system prompt with the assistants_info
    agent_configuration.system_prompt=SUPERVISOR_AGENT_INSTRUCTIONS.replace("{{ASSISTANTS}}", assistants_info_str)

    return SupervisorAssistant(
        name="supervisor_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=[], # We don't need tools because we will load agents as tools.
        agents=assistants, # Agents will be loaded as tools.
        state=AgentSharedState(thread_id=8),
        configuration=agent_configuration,
        memory=MemorySaver()
    )

class SupervisorAssistant(Agent):
    def as_api(
            self, 
            router: APIRouter, 
            route_name: str = "supervisor", 
            name: str = "Supervisor Assistant", 
            description: str = "API endpoints to call the Supervisor assistant completion.", 
            description_stream: str = "API endpoints to call the Supervisor assistant stream completion.",
            tags: list[str] = []
        ):
        return super().as_api(router, route_name, name, description, description_stream, tags)
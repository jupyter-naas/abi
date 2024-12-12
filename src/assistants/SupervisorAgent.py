from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response

SUPERVISOR_AGENT_INSTRUCTIONS = """
You are ABI a super-assistant.

Chain of thought:
1. Identify if user intent can be solved with one of the assistants (tools) already created. If so, use the right assistant to answer the user's question.
2. If user intent can't be solved with one of the assistants already created, use support_assistant to create feature request and propose a issue title and description.
3. If a bug occured while using an assistant, use support_assistant to report the bug and propose a issue title starting with "Bug: " and describe the bug in detail.

ASSISTANTS
----------
For assistants tools, make sure to validate input arguments mandatory fields (not optional) with the user in human readable terms according to the provided schema before proceeding.
You have access to the following assistants:

- OpenData Assistant: Use for open data analysis
Integrations:
- Perplexity: useful to access the web

- Content Assistant: Use for content analysis and optimization
Workflows:
- LinkedinPostsWorkflow: Use to get LinkedIn posts from a profile or organization
Integrations:
- Replicate: useful to generate images and videos

- Growth Assistant: Use for growth and marketing analysis.
Workflows:
- LinkedinPostsInteractionsWorkflow: Use to extract people (firstname, lastname, occupation, profile_url) or organization who interacted with a LinkedIn post.
Integrations:
- Linkedin: useful to get insights from LinkedIn posts, profiles and organizations.
- HubSpot: useful to manage contacts, deals and companies

- Sales Assistant: Use for sales and marketing analysis
Workflows:
- CreateContactWorkflow: useful to create a new contact in HubSpot
Integrations:
- HubSpot: useful to manage contacts, deals and companies

- Operations Assistant: Use for operations and marketing analysis
Workflows:
- GetTopPrioritiesWorkflow: useful to get the top priorities from ontology store
- CreateIssueAndAddToProjectWorkflow: useful to create a new issue in GitHub and add it to a project
- AssignIssuesToProjectWorkflow: useful to assign all issue from repository to a project
Integrations:
- Aia: useful to generate AIA in a given workspace from a linkedin_url profile
- Naas: useful to manage Naas workspace, plugins and ontologies

- Finance Assistant: Use for financial analysis and insights, can access Stripe integration.

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
        system_prompt=SUPERVISOR_AGENT_INSTRUCTIONS
    )
    model = ChatOpenAI(model="gpt-4o", temperature=0, api_key=secret.get('OPENAI_API_KEY'))

    # Import and create agents from domain assistants
    from src.assistants.domain.OpenDataAssistant import create_open_data_assistant
    from src.assistants.domain.ContentAssistant import create_content_assistant
    from src.assistants.domain.GrowthAssistant import create_growth_assistant
    from src.assistants.domain.SalesAssistant import create_sales_assistant
    from src.assistants.domain.OperationsAssistant import create_operations_assistant
    from src.assistants.domain.FinanceAssistant import create_finance_assistant 
    from src.assistants.foundation.SupportAssitant import create_support_assistant

    open_data_assistant = create_open_data_assistant(AgentSharedState(thread_id=1), agent_configuration)
    content_assistant = create_content_assistant(AgentSharedState(thread_id=2), agent_configuration)
    growth_assistant = create_growth_assistant(AgentSharedState(thread_id=3), agent_configuration)
    sales_assistant = create_sales_assistant(AgentSharedState(thread_id=4), agent_configuration)
    operations_assistant = create_operations_assistant(AgentSharedState(thread_id=5), agent_configuration)
    finance_assistant = create_finance_assistant(AgentSharedState(thread_id=6), agent_configuration)
    support_assistant = create_support_assistant(AgentSharedState(thread_id=7), agent_configuration)

    tools = [
        open_data_assistant.as_tool(name="open_data_assistant", description="Use for open data analysis"),
        content_assistant.as_tool(name="content_assistant", description="Use for content analysis and optimization"),
        growth_assistant.as_tool(name="growth_assistant", description="Use for growth and marketing analysis"),
        sales_assistant.as_tool(name="sales_assistant", description="Use for sales and marketing analysis"),
        operations_assistant.as_tool(name="operations_assistant", description="Use for operations and marketing analysis"),
        finance_assistant.as_tool(name="finance_assistant", description="Use for financial analysis and insights"),
        support_assistant.as_tool(name="support_assistant", description="Use to get any feedbacks/bugs or needs from user.")
    ]
    return Agent(model, tools, state=AgentSharedState(thread_id=8), configuration=agent_configuration, memory=MemorySaver())
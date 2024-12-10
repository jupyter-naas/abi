from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.assistants.prompt import SUPER_ASSISTANT_INSTRUCTIONS

def create_agent():
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    from src.integrations import (
        GithubIntegration, PerplexityIntegration, LinkedinIntegration, 
        ReplicateIntegration, NaasIntegration, AiaIntegration, 
        HubSpotIntegration, StripeIntegration, GithubGraphqlIntegration
    )
    from src.workflows import tools as workflow_tools
    
    tools = [] + workflow_tools
    
    # Add integrations based on available credentials
    if github_token := secret.get('GITHUB_ACCESS_TOKEN'):
        tools += GithubIntegration.as_tools(GithubIntegration.GithubIntegrationConfiguration(access_token=github_token))
        tools += GithubGraphqlIntegration.as_tools(GithubGraphqlIntegration.GithubGraphqlIntegrationConfiguration(access_token=github_token))
    
    if perplexity_key := secret.get('PERPLEXITY_API_KEY'):
        tools += PerplexityIntegration.as_tools(PerplexityIntegration.PerplexityIntegrationConfiguration(api_key=perplexity_key))
    
    if (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        tools += LinkedinIntegration.as_tools(LinkedinIntegration.LinkedinIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid))
    
    if replicate_key := secret.get('REPLICATE_API_KEY'):
        tools += ReplicateIntegration.as_tools(ReplicateIntegration.ReplicateIntegrationConfiguration(api_key=replicate_key))

    if naas_key := secret.get('NAAS_API_KEY'):
        tools += NaasIntegration.as_tools(NaasIntegration.NaasIntegrationConfiguration(api_key=naas_key))

    if (naas_key := secret.get('NAAS_API_KEY')) and (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        tools += AiaIntegration.as_tools(AiaIntegration.AiaIntegrationConfiguration(api_key=naas_key))

    if hubspot_token := secret.get('HUBSPOT_ACCESS_TOKEN'):
        tools += HubSpotIntegration.as_tools(HubSpotIntegration.HubSpotIntegrationConfiguration(access_token=hubspot_token))

    if stripe_key := secret.get('STRIPE_API_KEY'):
        tools += StripeIntegration.as_tools(StripeIntegration.StripeIntegrationConfiguration(api_key=stripe_key))
            
    return Agent(model, tools, configuration=AgentConfiguration(system_prompt=SUPER_ASSISTANT_INSTRUCTIONS))

def create_graph_agent():
    agent_shared_state = AgentSharedState()
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}')
    )
    
    # Import and create agents from domain assistants
    from src.assistants.domain.OpenDataAssistant import create_open_data_assistant
    from src.assistants.domain.ContentAssistant import create_content_assistant
    from src.assistants.domain.GrowthAssistant import create_growth_assistant
    from src.assistants.domain.SalesAssistant import create_sales_assistant
    from src.assistants.domain.OperationsAssistant import create_operations_assistant
    from src.assistants.domain.FinanceAssistant import create_finance_assistant 
    from src.assistants.foundation.SupportAssitant import create_support_assistant
    
    model = ChatOpenAI(model="gpt-4o", temperature=0, api_key=secret.get('OPENAI_API_KEY'))

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

    agent_configuration.system_prompt = """
    You are ABI a super-assistant.

    Chain of thought:
    1. Identify if user intent can be solved with one of the assistants (tools) already created. If so, use the right assistant to answer the user's question.
    2. If user intent can't be solved with one of the assistants already created, use support_assistant to create feature request and propose a issue title and description.
    3. If a bug occured while using an assistant, use support_assistant to report the bug and propose a issue title starting with "Bug: " and describe the bug in detail.
    
    ASSISTANTS
    ----------
    For assistants tools, make sure to validate input arguments mandatory fields (not optional) with the user in human readable terms according to the provided schema before proceeding.
    You have access to the following assistants:

    - OpenData Assistant: Use for open data analysis, can access the web through Perplexity integration.

    - Content Assistant: Use for content analysis and optimization, can access the web through Perplexity integration, Replicate integration and Linkedin integration.

    - Growth Assistant: Use for growth and marketing analysis, can access Linkedin integration and Hubspot integration.

    - Sales Assistant: Use for sales and marketing analysis, can access Hubspot integration.

    - Operations Assistant: Use for operations and marketing analysis
    Workflows:
    - GetTopPrioritiesWorkflow: useful to get the top priorities from Task and Project management tools
    - CreateIssueAndAddToProjectWorkflow: useful to create a new issue and add it to a project
    - AssignIssuesToProjectWorkflow: useful to assign all issue from repository to a project
    Integration:
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
    return Agent(model, tools, state=AgentSharedState(thread_id=8), configuration=agent_configuration, memory=MemorySaver())
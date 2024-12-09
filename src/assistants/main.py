from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.assistants.prompt import SUPER_ASSISTANT_INSTRUCTIONS

SUPER_ASSISTANT_INSTRUCTIONS_ABI = SUPER_ASSISTANT_INSTRUCTIONS.format(
    name="Abi",
    role="Super AI Assistant by NaasAI Research",
    description="A cutting-edge AI assistant developed by the research team at NaasAI, focused on providing maximum value and support to users. Combines deep technical expertise with emotional intelligence to deliver the most helpful experience possible."
)
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
            
    return Agent(model, tools, configuration=AgentConfiguration(system_prompt=SUPER_ASSISTANT_INSTRUCTIONS_ABI))


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
        support_assistant.as_tool(name="support_assistant", description="User support and issue handling")
    ]
    
    agent_configuration.system_prompt = SUPER_ASSISTANT_INSTRUCTIONS_ABI + """
        - Use open_data_assistant for external data analysis with Perplexity and Replicate Integrations.  
        - Use content_assistant for content strategy and analysis with Linkedin, Perplexity and Replicate Integrations.   
        - Use growth_assistant for marketing and growth insights with HubSpot Integration.
        - Use sales_assistant for sales and marketing analysis with HubSpot and Stripe Integrations.
        - Use operations_assistant for operations and marketing analysis with Github and Github Graphql Integrations.
        - Use finance_assistant for financial data and transactions with Stripe Integrations.
        - Use support_assistant if you can't answer user intent with all the assistants already created or if user ask for a new tool, integration or workflow.
        """
    return Agent(model, tools, state=AgentSharedState(thread_id=8), configuration=agent_configuration, memory=MemorySaver())
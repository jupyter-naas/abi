from src.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from langchain_openai import ChatOpenAI
from src.assistants.custom.support_agent import create_support_agent
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src.assistants.prompts import SUPER_ASSISTANT_INSTRUCTIONS
from src import secret

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
    
    # Import and create agents from custom module
    from src.assistants.custom.integration_agent import create_integration_agent
    from src.assistants.custom.workflow_agent import create_workflow_agent
    from src.assistants.custom.support_agent import create_support_agent
    
    integration_agent = create_integration_agent(AgentSharedState(thread_id=1), agent_configuration)
    workflow_agent = create_workflow_agent(AgentSharedState(thread_id=2), agent_configuration)
    support_agent = create_support_agent(AgentSharedState(thread_id=3), agent_configuration)
    
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    tools = [
        workflow_agent.as_tool(name="workflow_agent", description="ALWAYS CALL THIS FIRST"),
        integration_agent.as_tool(name="integration_agent", description="THEN CALL THIS IF workflow_agent DID NOT RETURN THE RESULT YOU WANTED"),
        support_agent.as_tool(name="support_agent", description="Use this for additional support if needed")
    ]
    
    agent_configuration.system_prompt = "You are a helpful assistant. Always use the workflow_agent first, then use the integration_agent if the result is not what you want. IF workflow_agent FAILS you must use the integration_agent to get the result you want. Use support_agent for additional assistance if needed."
    
    return Agent(model, tools, state=AgentSharedState(thread_id=4), configuration=agent_configuration, memory=MemorySaver()) 
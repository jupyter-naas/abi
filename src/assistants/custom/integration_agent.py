from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src.integrations import GithubIntegration, PerplexityIntegration, LinkedinIntegration, GithubGraphqlIntegration, ReplicateIntegration, NaasIntegration, AiaIntegration, HubSpotIntegration, StripeIntegration
from src import secret

def create_custom_integration_agent(agent_shared_state: AgentSharedState, agent_configuration: AgentConfiguration):
    """Creates a custom integration agent with specific tools.
    
    Args:
        agent_shared_state (AgentSharedState): Shared state for the agent
        agent_configuration (AgentConfiguration): Configuration for the agent
        
    Returns:
        Agent: Configured integration agent
    """
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    tools = []
    
    # Add integrations based on available credentials
    if github_token := secret.get('GITHUB_ACCESS_TOKEN'):
        tools += GithubIntegration.as_tools(
            GithubIntegration.GithubIntegrationConfiguration(access_token=github_token)
        )
        tools += GithubGraphqlIntegration.as_tools(
            GithubGraphqlIntegration.GithubGraphqlIntegrationConfiguration(access_token=github_token)
        )
    
    if perplexity_key := secret.get('PERPLEXITY_API_KEY'):
        tools += PerplexityIntegration.as_tools(
            PerplexityIntegration.PerplexityIntegrationConfiguration(api_key=perplexity_key)
        )
    
    if (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        tools += LinkedinIntegration.as_tools(
            LinkedinIntegration.LinkedinIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid)
        )
    
    if replicate_key := secret.get('REPLICATE_API_KEY'):
        tools += ReplicateIntegration.as_tools(
            ReplicateIntegration.ReplicateIntegrationConfiguration(api_key=replicate_key)
        )

    if naas_key := secret.get('NAAS_API_KEY'):
        tools += NaasIntegration.as_tools(
            NaasIntegration.NaasIntegrationConfiguration(api_key=naas_key)
        )

    if (naas_key := secret.get('NAAS_API_KEY')) and (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        tools += AiaIntegration.as_tools(
            AiaIntegration.AiaIntegrationConfiguration(api_key=naas_key)
        )

    if hubspot_token := secret.get('HUBSPOT_ACCESS_TOKEN'):
        tools += HubSpotIntegration.as_tools(
            HubSpotIntegration.HubSpotIntegrationConfiguration(access_token=hubspot_token)
        )

    if stripe_key := secret.get('STRIPE_API_KEY'):
        tools += StripeIntegration.as_tools(
            StripeIntegration.StripeIntegrationConfiguration(api_key=stripe_key)
        )
    
    return Agent(
        model, 
        tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 
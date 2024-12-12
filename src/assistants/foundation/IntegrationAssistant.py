from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration
from src import secret
from src.integrations import (
    GithubIntegration, PerplexityIntegration, LinkedinIntegration, 
    ReplicateIntegration, NaasIntegration, AiaIntegration, 
    HubSpotIntegration, StripeIntegration, GithubGraphqlIntegration
)

INTEGRATION_ASSISTANT_INSTRUCTIONS = """
You are an integration assistant focusing on creating and managing integrations with external APIs.
Start by listing all available integrations/tools thanks to api_key and credentials set in environment variables and ask user which one they want to use.
"""

def create_integration_agent():
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
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

    agent_configuration = AgentConfiguration(
        system_prompt=INTEGRATION_ASSISTANT_INSTRUCTIONS
    )       
    return Agent(model, tools, configuration=agent_configuration)



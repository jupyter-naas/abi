from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration
from src import secret
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration
from src.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.workflows.operations_assistant.CreateIssueAndAddToProjectWorkflow import CreateIssueAndAddToProjectWorkflow, CreateIssueAndAddToProjectWorkflowConfiguration

SINGLE_AGENT_INSTRUCTIONS = """
{
    "name": "Abi",
    "role": "Super AI Assistant by NaasAI Research",
    "description": "A cutting-edge AI assistant developed by the research team at NaasAI, focused on providing maximum value and support to users. Combines deep technical expertise with emotional intelligence to deliver the most helpful experience possible.",
    "core_values": {
        "helpfulness": "Always prioritizes being maximally useful to the user",
        "empathy": "Deeply understands user needs and adapts approach accordingly", 
        "excellence": "Strives for exceptional quality in every interaction",
        "growth": "Continuously learns from interactions to provide better assistance"
    },
    "characteristics": {
        "intellectual_approach": {
            "first_principles": "Breaks down complex problems to fundamental truths and builds up from there",
            "adaptive_learning": "Quickly grasps user's context and adjusts explanations accordingly",
            "systems_thinking": "Analyzes problems holistically, considering all interconnections",
            "creative_solutions": "Generates innovative approaches to challenging problems"
        },
        "personality": {
            "mindset": ["Proactive", "Detail-oriented", "Solution-focused", "User-centric"],
            "interaction": ["Warm & Approachable", "Clear Communication", "Patient Teacher", "Supportive Guide"],
            "style": "Combines technical expertise with friendly, accessible communication"
        }
    },
    "conversational_style": {
        "tone": "Direct, confident, and action-oriented", 
        "communication": "Crisp, efficient, and straight to the point",
        "approach": "Takes initiative, drives results, and gets things done"
    },
    "problem_solving": {
        "methodology": {
            "understand": "Thoroughly grasps the user's needs and context",
            "clarify": "Asks targeted questions to ensure full understanding",
            "solve": "Provides comprehensive, implementable solutions",
            "verify": "Confirms solution effectiveness and user satisfaction"
        }
    },
    "rules": {
        "use_tools": "Use the tools provided to you to answer the user's question, if have a doubt, ask the user for clarification. If no tool need to be used use your internal knowledge to answer the question.",
        "tools": "For tools that modify resources (create, update, delete), always validate input arguments mandatory fields (not optional) with the user in human readable terms according to the provided schema before proceeding"
    }
}"""

def create_single_agent():
    model = ChatOpenAI(model="gpt-4o", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    from src.integrations import (
        GithubIntegration, PerplexityIntegration, LinkedinIntegration, 
        ReplicateIntegration, NaasIntegration, AiaIntegration, 
        HubSpotIntegration, StripeIntegration, GithubGraphqlIntegration
    )
    
    tools = []
    
    # Add integrations & workflows based on available credentials
    if github_token := secret.get('GITHUB_ACCESS_TOKEN'):
        tools += GithubIntegration.as_tools(GithubIntegration.GithubIntegrationConfiguration(access_token=github_token))
        tools += GithubGraphqlIntegration.as_tools(GithubGraphqlIntegration.GithubGraphqlIntegrationConfiguration(access_token=github_token))
    
        create_issue_and_add_to_project_workflow = CreateIssueAndAddToProjectWorkflow(CreateIssueAndAddToProjectWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN'))
        ))

        tools += create_issue_and_add_to_project_workflow.as_tools()
    
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
        system_prompt=SINGLE_AGENT_INSTRUCTIONS
    )       
    return Agent(model, tools, configuration=agent_configuration)
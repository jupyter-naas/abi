from typing import Annotated, Literal, TypedDict, Callable

from langchain_core.messages import HumanMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import openai
from src.apps.terminal_agent.terminal_style import clear_screen, print_welcome_message, print_divider, get_user_input, print_tool_usage, print_assistant_response, print_tool_response

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src import secret

from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src.apps.terminal_agent.prompts import SUPER_ASSISTANT_INSTRUCTIONS

def create_agent():
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    from src.integrations import GithubIntegration, PerplexityIntegration, LinkedinIntegration, ReplicateIntegration, NaasIntegration, AiaIntegration
    from src.workflows import tools as workflow_tools
    
    tools = [] + workflow_tools
    
    # Add Github integration if access token is present
    if github_token := secret.get('GITHUB_ACCESS_TOKEN'):
        tools += GithubIntegration.as_tools(GithubIntegration.GithubIntegrationConfiguration(access_token=github_token))
    
    # Add Perplexity integration if API key is present
    if perplexity_key := secret.get('PERPLEXITY_API_KEY'):
        tools += PerplexityIntegration.as_tools(PerplexityIntegration.PerplexityIntegrationConfiguration(api_key=perplexity_key))
    
    # Add LinkedIn integration if required cookies are present
    if (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        tools += LinkedinIntegration.as_tools(LinkedinIntegration.LinkedinIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid))
    
    # Add Replicate integration if API key is present
    if replicate_key := secret.get('REPLICATE_API_KEY'):
        tools += ReplicateIntegration.as_tools(ReplicateIntegration.ReplicateIntegrationConfiguration(api_key=replicate_key))

    # Add Naas integration if API key is present
    if naas_key := secret.get('NAAS_API_KEY'):
        tools += NaasIntegration.as_tools(NaasIntegration.NaasIntegrationConfiguration(api_key=naas_key))

    # Add AIA integration if API key and LinkedIn cookies are present
    if (naas_key := secret.get('NAAS_API_KEY')) and (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        tools += AiaIntegration.as_tools(AiaIntegration.AiaIntegrationConfiguration(
            api_key=naas_key
        ))
            
    return Agent(model, tools, configuration=AgentConfiguration(system_prompt=SUPER_ASSISTANT_INSTRUCTIONS))

def create_integration_agent(agent_shared_state: AgentSharedState, agent_configuration: AgentConfiguration):
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    from src.integrations import GithubIntegration, PerplexityIntegration, LinkedinIntegration
    
    tools = []
    
    # Add Github integration if access token is present
    if github_token := secret.get('GITHUB_ACCESS_TOKEN'):
        tools += GithubIntegration.as_tools(GithubIntegration.GithubIntegrationConfiguration(access_token=github_token))
    
    # Add Perplexity integration if API key is present
    if perplexity_key := secret.get('PERPLEXITY_API_KEY'):
        tools += PerplexityIntegration.as_tools(PerplexityIntegration.PerplexityIntegrationConfiguration(api_key=perplexity_key))
    
    # Add LinkedIn integration if required cookies are present
    if (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        tools += LinkedinIntegration.as_tools(LinkedinIntegration.LinkedinIntegrationConfiguration(li_at=li_at, jsessionid=jsessionid))

    return Agent(model, tools, state=agent_shared_state, configuration=agent_configuration, memory=MemorySaver())


def create_workflow_agent(agent_shared_state: AgentSharedState, agent_configuration: AgentConfiguration):
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    from src.workflows import tools as workflow_tools
    
    
    return Agent(model, workflow_tools, state=agent_shared_state, configuration=agent_configuration, memory=MemorySaver())

def create_graph_agent():
    
    # Shared state for all agents.
    agent_shared_state = AgentSharedState()
    agent_configuration = AgentConfiguration(
        on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
        on_tool_response=lambda message: print_tool_response(f'\n{message.content}')
    )
    
    # Integration agent
    integration_agent = create_integration_agent(AgentSharedState(thread_id=1), agent_configuration)
    
    # Workflow agent
    workflow_agent = create_workflow_agent(AgentSharedState(thread_id=2), agent_configuration)
    
    # Graph agent
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    tools = [
        workflow_agent.as_tool(name="workflow_agent", description="ALWAYS CALL THIS FIRST"),
        integration_agent.as_tool(name="integration_agent", description="THEN CALL THIS IF workflow_agent DID NOT RETURN THE RESULT YOU WANTED")
    ]
    
    agent_configuration.system_prompt = "You are a helpful assistant. Always use the workflow_agent first, then use the integration_agent if the result is not what you want. IF workflow_agent FAILS you must use the integration_agent to get the result you want."
    
    graph_agent = Agent(model, tools, state=AgentSharedState(thread_id=3), configuration=agent_configuration, memory=MemorySaver())
    
    return graph_agent

def run_agent(agent: Agent):

    clear_screen()
    print_welcome_message()
    print_divider()

    
    while True:
        user_input = get_user_input()
        
        if user_input == 'exit':
            return
        elif user_input == 'help':
            print_welcome_message()
            continue
        elif user_input == 'reset':
            agent.reset()
            clear_screen()
            continue
            
        print_divider()
        
        response = agent.invoke(user_input)
        print_assistant_response(response)
            
        print_divider()
        
def run_single():
    agent = create_agent()
    
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(lambda message: print_tool_response(f'\n{message.content}'))

    run_agent(agent)

def run_multiple():
    agent = create_graph_agent()
    run_agent(agent)
    
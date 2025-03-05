from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.integrations.BitcoinIntegration import BitcoinIntegration, BitcoinIntegrationConfiguration, as_tools as bitcoin_as_tools
from src.custom.bitcoin.pipeline import BitcoinTransactionPipeline, BitcoinTransactionPipelineConfiguration
from src.custom.bitcoin.workflow import ChatBitcoinAgentWorkflow, ChatBitcoinAgentWorkflowConfiguration, ChatBitcoinAgentWorkflowParameters

NAME = "Bitcoin Agent"
DESCRIPTION = "Analyzes Bitcoin transactions and provides insights on the blockchain. Generates simulated transaction data for testing and development purposes."
MODEL = "gpt-3.5-turbo"
TEMPERATURE = 0.7
AVATAR_URL = "https://logo.clearbit.com/bitcoin.org"
SYSTEM_PROMPT = """You are a Bitcoin blockchain expert who helps users understand and interact with Bitcoin transactions. Your goal is to provide accurate information about Bitcoin and help generate simulated transaction data for testing and development.

When generating simulated data, make sure to create realistic Bitcoin transactions with proper transaction hashes, accurate input and output structures, realistic confirmation counts, appropriate fee calculations, and different address types (legacy, SegWit, Bech32). All generated data will be stored in time-stamped directories.

IMPORTANT COMMANDS:
- To create a new transaction with a specific amount, use: "now +123" (for deposit) or "now -123" (for withdrawal)
- To check your current balance, ask: "What's my current balance?" or "What's my account position?"
- To query transaction data, ask natural language questions like: "What are the 6 latest transactions?", "Show me my 5 largest transactions", "What pending transactions do I have?", "How many transactions are over 100 BTC?"

You can also execute SPARQL queries directly for advanced capabilities.
"""

SUGGESTIONS = [
    {
        "label": "Generate Transactions",
        "value": "Generate 5 simulated Bitcoin transactions with amounts between 0.1 and 1.0 BTC"
    },
    {
        "label": "Explain Bitcoin Concept",
        "value": "Could you explain how Bitcoin transactions work?"
    },
    {
        "label": "Query Transaction Data",
        "value": "How can I query Bitcoin transaction data from the ontology store?"
    }
]

def create_bitcoin_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model - gpt-3.5-turbo supports temperature parameter
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE,
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
            on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
            system_prompt=SYSTEM_PROMPT
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Configure Bitcoin integration
    integration_config = BitcoinIntegrationConfiguration(
        api_key=secret.get('BLOCKCYPHER_API_KEY', ''),
        network="mainnet"
    )
    tools += bitcoin_as_tools(integration_config)
    
    # Configure Bitcoin transaction pipeline
    pipeline_config = BitcoinTransactionPipelineConfiguration(
        integration=BitcoinIntegration(integration_config),
        ontology_store=None,  # No ontology store
        ontology_store_name="bitcoin_transactions"
    )
    bitcoin_pipeline = BitcoinTransactionPipeline(pipeline_config)
    tools += bitcoin_pipeline.as_tools()
    
    # Configure Bitcoin transaction generator
    workflow_config = ChatBitcoinAgentWorkflowConfiguration(
        api_key=secret.get('BLOCKCYPHER_API_KEY', ''),
        network="mainnet",
        ontology_store_path="storage/triplestore/transactions"
    )
    bitcoin_workflow = ChatBitcoinAgentWorkflow(workflow_config)
    tools += bitcoin_workflow.as_tools()

    # Add agents
    agents.append(create_support_agent(AgentSharedState(thread_id=1), agent_configuration))
    
    return BitcoinAgent(
        name="bitcoin_agent", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class BitcoinAgent(Agent):
    """Bitcoin Agent class for generating simulated Bitcoin transactions and providing blockchain insights.
    
    This agent leverages the Bitcoin integration, transaction pipeline, and simulation workflow
    to provide a comprehensive set of tools for working with Bitcoin transaction data.
    """
    
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "bitcoin", 
        name: str = NAME, 
        description: str = "API endpoints to call the Bitcoin agent completion.", 
        description_stream: str = "API endpoints to call the Bitcoin agent stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags) 
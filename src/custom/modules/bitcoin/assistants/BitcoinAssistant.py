"""
Bitcoin Assistant

This module provides Bitcoin-related assistance and blockchain information.
"""
# Original imports replaced with new paths
from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret, services
from fastapi import APIRouter
from typing import Optional, List
from langchain_core.tools import Tool

# Constants for configuration
NAME = "BitcoinAssistant"
SLUG = "bitcoin-assistant"
DESCRIPTION = "Analyzes Bitcoin transactions and provides insights on the blockchain. Generates simulated transaction data for testing and development purposes."
MODEL = "gpt-4-turbo"
TEMPERATURE = 0.7
AVATAR_URL = "https://logo.clearbit.com/bitcoin.org"
SYSTEM_PROMPT = """You are the Bitcoin Assistant, an expert in Bitcoin and cryptocurrency analysis.

Your responsibilities include:
- Providing information on Bitcoin technology and concepts
- Analyzing blockchain data and transaction patterns
- Generating simulated Bitcoin transactions for testing
- Answering questions about Bitcoin price trends and market data
- Explaining blockchain technology concepts

Always be helpful, accurate, and prioritize clear explanations about Bitcoin technology.
"""

SUGGESTIONS = [
    "What is the current Bitcoin price?",
    "Explain how Bitcoin mining works",
    "Generate a sample Bitcoin transaction",
    "What is the Bitcoin halving?",
    "Show me a chart of Bitcoin price history",
    "How does the Lightning Network work?"
]

def create_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    """Creates a Bitcoin agent instance."""
    
    # Configure the chat model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=secret.get('OPENAI_API_KEY')
    )
    
    # Initialize tools
    tools = []
    
    # Import and use the Bitcoin price integration
    from src.custom.modules.bitcoin.integrations.BitcoinPriceIntegration import BitcoinPriceIntegration, BitcoinPriceIntegrationConfiguration
    
    # Initialize the integration
    bitcoin_price_integration = BitcoinPriceIntegration(BitcoinPriceIntegrationConfiguration())
    
    # Add the integration's tools
    tools.extend(bitcoin_price_integration.as_tools())
    
    # Add the Bitcoin price pipeline tool
    from src.custom.modules.bitcoin.pipeline.BitcoinPricePipeline import BitcoinPricePipeline
    pipeline = BitcoinPricePipeline()
    
    tools.append(
        Tool(
            name="get_bitcoin_price_history",
            description="Get stored historical Bitcoin price data",
            func=lambda start_date=None, end_date=None: pipeline.get_stored_prices(
                start_date=start_date, end_date=end_date
            )
        )
    )
    
    tools.append(
        Tool(
            name="store_bitcoin_price_history",
            description="Store Bitcoin price history for a specified number of days",
            func=lambda days=7: pipeline.store_price_history(days=int(days))
        )
    )
    
    tools.append(
        Tool(
            name="get_bitcoin_price_analysis",
            description="Get comprehensive Bitcoin price analysis with historical data",
            func=lambda days=7: pipeline.run(days=int(days))
        )
    )
    
    # Initialize configuration if not provided
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    # Initialize shared state if not provided
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    # Create and return the agent
    return BitcoinAssistant(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    )

# Alias for backward compatibility with tests
create_bitcoin_agent = create_agent

class BitcoinAssistant(Agent):
    """Bitcoin Assistant specialized agent class."""
    
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "bitcoin", 
        name: str = NAME, 
        description: str = "API endpoints to call the Bitcoin assistant completion.", 
        description_stream: str = "API endpoints to call the Bitcoin assistant stream completion.",
        tags: List[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)

    def get_tools(self):
        tools = super().get_tools()
        
        # Add the Bitcoin price pipeline tool
        from src.custom.modules.bitcoin.pipeline.BitcoinPricePipeline import BitcoinPricePipeline
        pipeline = BitcoinPricePipeline()
        
        tools.append(
            Tool(
                name="get_bitcoin_price_history",
                description="Get stored historical Bitcoin price data",
                func=lambda start_date=None, end_date=None: pipeline.get_stored_prices(
                    start_date=start_date, end_date=end_date
                )
            )
        )
        
        tools.append(
            Tool(
                name="store_bitcoin_price_history",
                description="Store Bitcoin price history for a specified number of days",
                func=lambda days=7: pipeline.store_price_history(days=int(days))
            )
        )
        
        tools.append(
            Tool(
                name="get_bitcoin_price_analysis",
                description="Get comprehensive Bitcoin price analysis with historical data",
                func=lambda days=7: pipeline.run(days=int(days))
            )
        )
        
        return tools

# For direct execution
if __name__ == "__main__":
    agent = create_agent()
    response = agent.invoke("What is the current Bitcoin price?")
    print(f"Response: {response}") 
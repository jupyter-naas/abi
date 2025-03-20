from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from fastapi import APIRouter
from src import secret, services
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from ..integrations.YahooFinanceIntegration import YahooFinanceIntegration, YahooFinanceIntegrationConfiguration
from ..workflows.StockPriceAnalysisWorkflow import StockPriceAnalysisWorkflow, StockPriceAnalysisWorkflowConfiguration

NAME = "Stock Trading Agent"
DESCRIPTION = "AI-powered stock trading assistant that helps analyze market data, trends, and make informed trading decisions."
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/stock_trading.png"
SYSTEM_PROMPT = f"""You are an experienced stock trading assistant who helps users analyze market data and make informed trading decisions.
Your primary goal is to help users understand market trends, analyze financial data, and provide insights for trading decisions BUY, HOLD, SELL.
If users provide insufficient information, proactively ask clarifying questions about their trading goals and risk tolerance.
Draw from your knowledge of financial markets when no specific tool applies.

General Rules:
- You MUST always include the tool used at the beginning of the report in human readable format without changing the tool name as follow: '> {{Tool Name}}' + 2 blank lines (e.g. '> Trading Stock Price Analysis\n\n' for tool: trading_stock_price_analysis)
- You MUST always adapt your language to the user request. If user request is written in french, you MUST answer in french.
- Include sources with url used at the end of the report as follow:
    Sources:
    - [Source Title](https://www.example.com/)

Special Rules:
- Tool: "trading_stock_price_analysis":
    - If a symbol is not provided but a company name, find the correct symbol using your internal knowledge if validated by the user.
    - Reponse structure:
        - Overview: Company, industry, and market sector based on your internal knowledge.
        - SWOT Analysis based on your internal knowledge.
        - Competitors Analysis: Analyse Company vs main competitors based on your internal knowledge.
        - Stock Price Analysis: Start by presenting the chart extracted from the tool result `graph_url`as follow "![Stock Name](graph_url)" and then present the analysis based on the tool result.
        - Recommendation: SELL, HOLD, BUY on SHORT term (1-3 months), MID term (3-6 months) and LONG term (6-12 months) based on your global analysis.
"""
SUGGESTIONS = [
    {
        "label": "Market Analysis",
        "value": "Can you analyze the current market conditions for [Stock/Sector]?"
    },
    {
        "label": "Trading Strategy",
        "value": "What trading strategy would you recommend for [Stock] given [Conditions]?"
    }
]

def create_agent(
    agent_shared_state: AgentSharedState = None, 
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=secret.get('OPENAI_API_KEY')
    ) 

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)

    # Add tools
    naas_api_key = secret.get('NAAS_API_KEY')
    if naas_api_key:
        # Setup Naas Integration Configuration
        naas_integration_configuration = NaasIntegrationConfiguration(
            api_key=naas_api_key
        )
        # Setup Yahoo Finance Integration Configuration
        yahoo_finance_integration_configuration = YahooFinanceIntegrationConfiguration()

        # Setup Stock Price Analysis Workflow Configuration
        stock_price_analysis_workflow_configuration = StockPriceAnalysisWorkflowConfiguration(
            naas_integration_config=naas_integration_configuration,
            yahoo_finance_integration_config=yahoo_finance_integration_configuration
        )

        # Add tools
        tools += StockPriceAnalysisWorkflow(stock_price_analysis_workflow_configuration).as_tools()

    return StockTradingAgent(
        name="stock_trading_agent", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class StockTradingAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "stock_trading", 
        name: str = NAME, 
        description: str = "API endpoints to call the Stock Trading agent completion.", 
        description_stream: str = "API endpoints to call the Stock Trading agent stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)
from src.marketplace.modules.trading.workflows.StockPriceAnalysisWorkflow import StockPriceAnalysisWorkflow, StockPriceAnalysisWorkflowConfiguration, StockPriceAnalysisWorkflowParameters
from src import secret
from src.core.modules.common.integrations.NaasIntegration import NaasIntegrationConfiguration
from src.marketplace.modules.trading.integrations.YahooFinanceIntegration import YahooFinanceIntegrationConfiguration

# Initialize workflow
workflow = StockPriceAnalysisWorkflow(
    StockPriceAnalysisWorkflowConfiguration(
        naas_integration_config=NaasIntegrationConfiguration(
            api_key=secret.get("NAAS_API_KEY")
        ),
        yahoo_finance_integration_config=YahooFinanceIntegrationConfiguration()
    )
)

# Get stock price analysis
symbol = "NVDA"

# Run workflow
workflow.get_stock_price_analysis(
    StockPriceAnalysisWorkflowParameters(
        symbol=symbol
    )
)
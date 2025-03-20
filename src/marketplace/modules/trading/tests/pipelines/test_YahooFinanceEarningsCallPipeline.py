from src.marketplace.modules.trading.integrations.YahooFinanceIntegration import YahooFinanceIntegration, YahooFinanceIntegrationConfiguration

# Initialize integrations
yahoo_finance_integration = YahooFinanceIntegration(YahooFinanceIntegrationConfiguration())

# Get earnings call data
earnings_call_data = yahoo_finance_integration.get_earnings_calls("AAPL")
print(earnings_call_data)

from src.marketplace.modules.trading.pipelines.YahooFinanceEarningsCallPipeline import YahooFinanceEarningsCallPipeline, YahooFinanceEarningsCallPipelineConfiguration, YahooFinanceEarningsCallPipelineParameters
from src import services

# Initialize ontology store
ontology_store = services.ontology_store_service

# Initialize pipeline
pipeline_configuration = YahooFinanceEarningsCallPipelineConfiguration(
    ontology_store=ontology_store,
)
pipeline = YahooFinanceEarningsCallPipeline(pipeline_configuration)

# Run pipeline
result = pipeline.run(YahooFinanceEarningsCallPipelineParameters(data=earnings_call_data))
print(result)
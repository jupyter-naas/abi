from src import secret, services
from src.marketplace.modules.trading.integrations.YahooFinanceIntegration import YahooFinanceIntegrationConfiguration
from src.marketplace.modules.trading.pipelines.YahooFinanceEarningsCallPipeline import YahooFinanceEarningsCallPipelineConfiguration
from src.marketplace.modules.trading.workflows.GetEarningsCallWorkflow import GetEarningsCallWorkflow, GetEarningsCallWorkflowConfiguration, GetEarningsCallWorkflowParameters

# Init integration configuration
yahoo_finance_integration_config = YahooFinanceIntegrationConfiguration()

# Init ontology store
ontology_store = services.ontology_store_service

# Init pipeline configuration
pipeline_config = YahooFinanceEarningsCallPipelineConfiguration(
    ontology_store=ontology_store
)

# Init workflow configuration
workflow_config = GetEarningsCallWorkflowConfiguration(
    yahoo_finance_integration_config=yahoo_finance_integration_config,
    yahoo_finance_earnings_call_pipeline_config=pipeline_config,
    ontology_store=ontology_store
)

# Initialize workflow
workflow = GetEarningsCallWorkflow(workflow_config)

# Get stock price analysis
symbol = "AVGO"

# Run workflow
workflow.get_earnings_call_data(
    GetEarningsCallWorkflowParameters(
        symbol=symbol
    )
)
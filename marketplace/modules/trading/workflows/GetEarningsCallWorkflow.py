from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src.marketplace.modules.trading.integrations.YahooFinanceIntegration import YahooFinanceIntegration, YahooFinanceIntegrationConfiguration
from src.marketplace.modules.trading.pipelines.YahooFinanceEarningsCallPipeline import YahooFinanceEarningsCallPipeline, YahooFinanceEarningsCallPipelineConfiguration, YahooFinanceEarningsCallPipelineParameters
from abi import logger
from datetime import datetime

@dataclass
class GetEarningsCallWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for GetEarningsCallWorkflow.
    
    Attributes:
        yahoo_finance_integration_config: YahooFinanceIntegrationConfiguration
        ontology_store: IOntologyStoreService
    """
    yahoo_finance_integration_config: YahooFinanceIntegrationConfiguration
    yahoo_finance_earnings_call_pipeline_config: YahooFinanceEarningsCallPipelineConfiguration
    ontology_store: IOntologyStoreService

class GetEarningsCallWorkflowParameters(WorkflowParameters):
    """Parameters for getting earnings call data.
    """
    symbol: str = Field(..., description="The symbol of the company to get earnings call data for.")

class GetEarningsCallWorkflow(Workflow):
    """Workflow for getting earnings call data.
    
    This workflow handles getting earnings call data.
    """
    
    __configuration: GetEarningsCallWorkflowConfiguration
    __yahoo_finance_integration: YahooFinanceIntegration
    __yahoo_finance_earnings_call_pipeline: YahooFinanceEarningsCallPipeline

    def __init__(self, configuration: GetEarningsCallWorkflowConfiguration):
        self.__configuration = configuration
        self.__yahoo_finance_integration = YahooFinanceIntegration(configuration.yahoo_finance_integration_config)
        self.__yahoo_finance_earnings_call_pipeline = YahooFinanceEarningsCallPipeline(configuration.yahoo_finance_earnings_call_pipeline_config)
        self.__ontology_store = configuration.ontology_store
        
    def get_earnings_call_data(self, parameters: GetEarningsCallWorkflowParameters) -> str:
        # Get earnings call data
        earnings_call_data = self.__yahoo_finance_integration.get_earnings_calls(parameters.symbol)

        # Send data to ontology store (pipeline)
        self.__yahoo_finance_earnings_call_pipeline.run(YahooFinanceEarningsCallPipelineParameters(data=earnings_call_data))

        # Check if the symbol exists in the ontology store
        query = f"""
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?Symbol ?Company ?Earnings_Date ?EPS_Estimate ?Reported_EPS ?Surprise_Percentage
        WHERE {{
        ?tickerEntity a abi:Ticker ;
            rdfs:label ?Symbol ;
            abi:isTickerSymbolOf ?company .
        
        ?company rdfs:label ?Company .
        
        FILTER(?Symbol = "{parameters.symbol}"@en)

        # Get earnings call and EPS data
        ?company abi:hostsEarningsCall ?call .
        ?call abi:hasEarningsPerShareData ?eps .
        ?call abi:occursAtTime ?timeRegion .
        ?timeRegion abi:alt_label ?Earnings_Date .
        # Get EPS details
        OPTIONAL {{
            ?eps abi:estimated_earnings_per_share ?EPS_Estimate ;
                abi:reported_earnings_per_share ?Reported_EPS ;
                abi:earnings_per_share_surprise_percentage ?Surprise_Percentage .
        }}
        }}
        ORDER BY DESC(?timeRegion)
        """
        results = self.__ontology_store.query(query)
        data = []
        for row in results:
            data_dict = {}
            for key in row.labels:
                data_dict[key] = str(row[key]) if row[key] else None
            data.append(data_dict)
        return data

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tools
        """
        return [
            StructuredTool(
                name="get_earnings_call_data",
                description="Get the earnings call data for a given symbol.",
                func=lambda **kwargs: self.get_earnings_call_data(GetEarningsCallWorkflowParameters(**kwargs)),
                args_schema=GetEarningsCallWorkflowParameters
            ),
            StructuredTool(
                name="get_current_datetime",
                description="Get the current datetime.",
                func=lambda **kwargs: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                args_schema=None
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
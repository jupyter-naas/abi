from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.custom.bitcoin_agent.integration import BitcoinIntegration, BitcoinIntegrationConfiguration
from src.custom.bitcoin_agent.pipeline import BitcoinTransactionPipeline, BitcoinTransactionPipelineConfiguration
from src import secret, config
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
import json

@dataclass
class BitcoinTransactionWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for BitcoinTransactionWorkflow.
    
    Attributes:
        api_key (str): API key for the Bitcoin blockchain service
        api_secret (Optional[str]): API secret for the service if required
        base_url (str): Base URL for the Bitcoin API service
        network (str): Bitcoin network to use (mainnet, testnet)
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use
    """
    api_key: str
    api_secret: Optional[str] = None
    base_url: str = "https://api.blockcypher.com/v1"
    network: str = "mainnet"
    ontology_store: IOntologyStoreService = None
    ontology_store_name: str = "bitcoin_transactions"

class BitcoinTransactionWorkflowParameters(WorkflowParameters):
    """Parameters for BitcoinTransactionWorkflow execution.
    
    Attributes:
        tx_hash (Optional[str]): Bitcoin transaction hash to process
        address (Optional[str]): Bitcoin address to process transactions for
        limit (int): Maximum number of transactions to process when using address
        fetch_details (bool): Whether to fetch detailed transaction data
    """
    tx_hash: Optional[str] = Field(None, description="Bitcoin transaction hash to process")
    address: Optional[str] = Field(None, description="Bitcoin address to process transactions for")
    limit: int = Field(10, description="Maximum number of transactions to process when using address")
    fetch_details: bool = Field(True, description="Whether to fetch detailed transaction data")

class BitcoinTransactionWorkflow(Workflow):
    __configuration: BitcoinTransactionWorkflowConfiguration
    
    def __init__(self, configuration: BitcoinTransactionWorkflowConfiguration):
        """Initialize Bitcoin transaction workflow with configuration."""
        self.__configuration = configuration
        
        # Initialize the Bitcoin integration
        integration_config = BitcoinIntegrationConfiguration(
            api_key=self.__configuration.api_key,
            api_secret=self.__configuration.api_secret,
            base_url=self.__configuration.base_url,
            network=self.__configuration.network
        )
        self.__integration = BitcoinIntegration(integration_config)
        
        # Initialize the pipeline if ontology store is provided
        self.__pipeline = None
        if self.__configuration.ontology_store:
            pipeline_config = BitcoinTransactionPipelineConfiguration(
                integration=self.__integration,
                ontology_store=self.__configuration.ontology_store,
                ontology_store_name=self.__configuration.ontology_store_name
            )
            self.__pipeline = BitcoinTransactionPipeline(pipeline_config)

    def run(self, parameters: BitcoinTransactionWorkflowParameters) -> Any:
        """Run the Bitcoin transaction workflow.
        
        This workflow can:
        1. Retrieve a single transaction by hash
        2. Retrieve transactions for an address
        3. Process transactions through the pipeline if ontology store is configured
        
        Args:
            parameters (BitcoinTransactionWorkflowParameters): Workflow parameters
            
        Returns:
            Any: Transaction data or processing result
            
        Raises:
            ValueError: If neither tx_hash nor address is provided
        """
        logger.info(f"Running Bitcoin transaction workflow with parameters: {parameters}")
        
        if not parameters.tx_hash and not parameters.address:
            raise ValueError("Either tx_hash or address must be provided")
        
        result = {}
        
        # Single transaction processing
        if parameters.tx_hash:
            logger.info(f"Fetching Bitcoin transaction with hash: {parameters.tx_hash}")
            tx_data = self.__integration.get_transaction(parameters.tx_hash)
            
            # Map to ontology format
            ontology_tx = self.__integration.map_to_transaction_ontology(tx_data)
            
            result = {
                "transaction": tx_data,
                "ontology_mapping": ontology_tx
            }
            
            # Run through pipeline if available
            if self.__pipeline:
                logger.info("Processing transaction through pipeline")
                pipeline_params = BitcoinTransactionPipelineParameters(
                    tx_hash=parameters.tx_hash
                )
                graph = self.__pipeline.run(pipeline_params)
                result["pipeline_result"] = "Transaction processed through pipeline and stored in ontology"
        
        # Address transactions processing
        elif parameters.address:
            logger.info(f"Fetching Bitcoin transactions for address: {parameters.address}")
            
            # First get basic address info
            address_info = self.__integration.get_address_info(parameters.address)
            
            transactions = []
            if parameters.fetch_details:
                # Get detailed transaction data
                txs = self.__integration.list_address_transactions(
                    parameters.address, parameters.limit
                )
                
                # Map each transaction to ontology format
                for tx in txs:
                    ontology_tx = self.__integration.map_to_transaction_ontology(tx)
                    transactions.append({
                        "transaction": tx,
                        "ontology_mapping": ontology_tx
                    })
            
            result = {
                "address_info": address_info,
                "transactions": transactions
            }
            
            # Run through pipeline if available
            if self.__pipeline:
                logger.info("Processing address transactions through pipeline")
                pipeline_params = BitcoinTransactionPipelineParameters(
                    address=parameters.address,
                    limit=parameters.limit
                )
                graph = self.__pipeline.run(pipeline_params)
                result["pipeline_result"] = f"{len(transactions)} transactions processed through pipeline and stored in ontology"
        
        return result

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tools
        """
        return [
            StructuredTool(
                name="get_bitcoin_transaction",
                description="Fetch and process a Bitcoin transaction by its hash",
                func=lambda tx_hash, fetch_details=True: self.run(BitcoinTransactionWorkflowParameters(
                    tx_hash=tx_hash,
                    fetch_details=fetch_details
                )),
                args_schema=BitcoinTransactionWorkflowParameters
            ),
            StructuredTool(
                name="get_bitcoin_address_transactions",
                description="Fetch and process Bitcoin transactions for an address",
                func=lambda address, limit=10, fetch_details=True: self.run(BitcoinTransactionWorkflowParameters(
                    address=address,
                    limit=limit,
                    fetch_details=fetch_details
                )),
                args_schema=BitcoinTransactionWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/bitcoin/transaction")
        def get_transaction(parameters: BitcoinTransactionWorkflowParameters):
            return self.run(parameters)
            
        @router.get("/bitcoin/transaction/{tx_hash}")
        def get_transaction_by_hash(tx_hash: str, fetch_details: bool = True):
            return self.run(BitcoinTransactionWorkflowParameters(
                tx_hash=tx_hash,
                fetch_details=fetch_details
            ))
            
        @router.get("/bitcoin/address/{address}/transactions")
        def get_address_transactions(
            address: str, 
            limit: int = 10, 
            fetch_details: bool = True
        ):
            return self.run(BitcoinTransactionWorkflowParameters(
                address=address,
                limit=limit,
                fetch_details=fetch_details
            )) 
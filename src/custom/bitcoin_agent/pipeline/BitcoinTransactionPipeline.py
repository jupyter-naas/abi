from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from src.custom.bitcoin_agent.integration import BitcoinIntegration
from abi.utils.Graph import ABIGraph
from rdflib import Graph, Literal, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, XSD
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src import secret
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from typing import List, Optional, Union
from pydantic import Field
from datetime import datetime
from rdflib.plugins.sparql import prepareQuery

# Define namespaces
ABI = Namespace("http://ontology.naas.ai/abi/")

@dataclass
class BitcoinTransactionPipelineConfiguration(PipelineConfiguration):
    """Configuration for BitcoinTransactionPipeline.
    
    Attributes:
        integration (BitcoinIntegration): The Bitcoin integration instance to use
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use. Defaults to "bitcoin_transactions"
    """
    integration: BitcoinIntegration
    ontology_store: Optional[IOntologyStoreService] = None
    ontology_store_name: str = "bitcoin_transactions"

class BitcoinTransactionPipelineParameters(PipelineParameters):
    """Parameters for BitcoinTransactionPipeline execution.
    
    Attributes:
        tx_hash (Optional[str]): Bitcoin transaction hash to process
        address (Optional[str]): Bitcoin address to process transactions for
        limit (int): Maximum number of transactions to process when using address
        before_block (Optional[int]): Only process transactions before this block height
    """
    tx_hash: Optional[str] = Field(None, description="Bitcoin transaction hash to process")
    address: Optional[str] = Field(None, description="Bitcoin address to process transactions for")
    limit: int = Field(10, description="Maximum number of transactions to process when using address")
    before_block: Optional[int] = Field(None, description="Only process transactions before this block height")

class BitcoinTransactionPipeline(Pipeline):
    __configuration: BitcoinTransactionPipelineConfiguration
    
    def __init__(self, configuration: BitcoinTransactionPipelineConfiguration):
        self.__configuration = configuration
        
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[StructuredTool]: List containing the pipeline tool
        """
        return [StructuredTool(
            name="bitcoin_transaction_pipeline",
            description="Processes Bitcoin transactions and maps them to the transaction ontology",
            func=lambda **kwargs: self.run(BitcoinTransactionPipelineParameters(**kwargs)),
            args_schema=BitcoinTransactionPipelineParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/BitcoinTransactionPipeline")
        def run(parameters: BitcoinTransactionPipelineParameters):
            return self.run(parameters).serialize(format="turtle")

    def run(self, parameters: BitcoinTransactionPipelineParameters) -> Graph:        
        """Run the Bitcoin transaction pipeline.
        
        This pipeline fetches Bitcoin transaction data and maps it to the Transaction ontology.
        It can process either a single transaction by hash or multiple transactions for an address.
        
        Args:
            parameters (BitcoinTransactionPipelineParameters): Pipeline parameters
            
        Returns:
            Graph: RDF graph containing the transaction data
            
        Raises:
            ValueError: If neither tx_hash nor address is provided
        """
        graph = ABIGraph()
        
        # Add prefixes for clarity
        graph.bind("abi", ABI)
        
        if parameters.tx_hash:
            # Process a single transaction
            tx_data = self.__configuration.integration.get_transaction(parameters.tx_hash)
            self._add_transaction_to_graph(graph, tx_data)
        elif parameters.address:
            # Process transactions for an address
            txs = self.__configuration.integration.list_address_transactions(
                parameters.address, 
                parameters.limit, 
                parameters.before_block
            )
            for tx_data in txs:
                self._add_transaction_to_graph(graph, tx_data)
        else:
            raise ValueError("Either tx_hash or address must be provided")
        
        # Store the graph in the ontology store if available
        if self.__configuration.ontology_store is not None:
            self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)
        
        return graph
    
    def _add_transaction_to_graph(self, graph: ABIGraph, tx_data: dict) -> None:
        """Add a Bitcoin transaction to the RDF graph using the Bitcoin ontology.
        
        Args:
            graph (ABIGraph): The RDF graph to add to
            tx_data (dict): Bitcoin transaction data
        """
        tx_hash = tx_data.get('hash')
        
        # Create transaction URI
        tx_uri = URIRef(f"http://ontology.naas.ai/abi/transactions/bitcoin/{tx_hash}")
        
        # Add transaction type (using the new Bitcoin ontology)
        graph.add((tx_uri, RDF.type, ABI.BitcoinTransaction))
        graph.add((tx_uri, RDF.type, ABI.OnChainTransaction))  # All BlockCypher transactions are on-chain
        graph.add((tx_uri, ABI.hasTransactionType, ABI.CashType))
        
        # Add transaction hash
        graph.add((tx_uri, ABI.transactionHash, Literal(tx_hash, datatype=XSD.string)))
        
        # Add transaction properties
        graph.add((tx_uri, RDFS.label, Literal(f"Bitcoin transaction {tx_hash[:8]}...", datatype=XSD.string)))
        graph.add((tx_uri, ABI.description, Literal(f"Bitcoin transaction {tx_hash}", datatype=XSD.string)))
        
        # Add network information
        network_type = ABI.BitcoinMainnet if self.__configuration.integration._configuration.network == "mainnet" else ABI.BitcoinTestnet
        graph.add((tx_uri, ABI.onNetwork, network_type))
        
        # Calculate total output amount in BTC (satoshis / 100000000)
        total_amount = sum([output.get("value", 0) for output in tx_data.get("outputs", [])]) / 100000000
        graph.add((tx_uri, ABI.amount, Literal(total_amount, datatype=XSD.decimal)))
        
        # Add currency (BTC)
        btc_uri = ABI.Bitcoin
        graph.add((tx_uri, ABI.hasCurrency, btc_uri))
        
        # Add status based on confirmations
        status = self._map_tx_status(tx_data)
        graph.add((tx_uri, ABI.hasStatus, status))
        
        # Add confirmation count
        confirmations = tx_data.get("confirmations", 0)
        graph.add((tx_uri, ABI.confirmations, Literal(confirmations, datatype=XSD.integer)))
        
        # Add block information if confirmed
        if tx_data.get("block_height"):
            # Create block URI
            block_height = tx_data.get("block_height")
            block_hash = tx_data.get("block_hash", f"unknown-{block_height}")
            block_uri = URIRef(f"http://ontology.naas.ai/abi/blocks/bitcoin/{block_hash}")
            
            # Add block properties
            graph.add((block_uri, RDF.type, ABI.BitcoinBlock))
            graph.add((block_uri, ABI.blockHeight, Literal(block_height, datatype=XSD.integer)))
            graph.add((block_uri, ABI.blockHash, Literal(block_hash, datatype=XSD.string)))
            
            # Link transaction to block
            graph.add((tx_uri, ABI.inBlock, block_uri))
            
            # Add block time if available
            if tx_data.get("confirmed"):
                block_time = datetime.fromtimestamp(tx_data.get("confirmed"))
                graph.add((block_uri, ABI.blockTime, Literal(block_time.isoformat(), datatype=XSD.dateTime)))
        
        # Add fee information
        if tx_data.get("fees") is not None:
            # Convert satoshis to BTC
            fees_btc = tx_data.get("fees", 0) / 100000000
            graph.add((tx_uri, ABI.transactionFee, Literal(fees_btc, datatype=XSD.decimal)))
        
        # Add transaction inputs
        for i, tx_input in enumerate(tx_data.get("inputs", [])):
            if "addresses" in tx_input:
                for address in tx_input.get("addresses", []):
                    # Create address URI and add it as a sender
                    sender_uri = self._add_address_to_graph(graph, address)
                    graph.add((tx_uri, ABI.hasSender, sender_uri))
                    
                    # Create input URI
                    input_uri = URIRef(f"http://ontology.naas.ai/abi/transactions/bitcoin/{tx_hash}/inputs/{i}")
                    graph.add((input_uri, RDF.type, ABI.BitcoinTransactionInput))
                    
                    # Link input to transaction
                    graph.add((tx_uri, ABI.hasTransactionInput, input_uri))
                    
                    # Add script signature if available
                    if tx_input.get("script"):
                        graph.add((input_uri, ABI.scriptSig, Literal(tx_input.get("script"), datatype=XSD.string)))
                        
                    # Add previous output reference if available
                    if tx_input.get("prev_hash") and tx_input.get("output_index") is not None:
                        prev_tx_hash = tx_input.get("prev_hash")
                        output_index = tx_input.get("output_index")
                        prev_output_uri = URIRef(f"http://ontology.naas.ai/abi/transactions/bitcoin/{prev_tx_hash}/outputs/{output_index}")
                        graph.add((input_uri, ABI.prevOutput, prev_output_uri))
        
        # Add transaction outputs
        for i, tx_output in enumerate(tx_data.get("outputs", [])):
            if "addresses" in tx_output:
                for address in tx_output.get("addresses", []):
                    # Create address URI and add it as a recipient
                    recipient_uri = self._add_address_to_graph(graph, address)
                    graph.add((tx_uri, ABI.hasRecipient, recipient_uri))
                    
                    # Create output URI
                    output_uri = URIRef(f"http://ontology.naas.ai/abi/transactions/bitcoin/{tx_hash}/outputs/{i}")
                    graph.add((output_uri, RDF.type, ABI.BitcoinTransactionOutput))
                    
                    # Link output to transaction
                    graph.add((tx_uri, ABI.hasTransactionOutput, output_uri))
                    
                    # Add output value
                    output_value_btc = tx_output.get("value", 0) / 100000000
                    graph.add((output_uri, ABI.outputValue, Literal(output_value_btc, datatype=XSD.decimal)))
                    
                    # Link output to recipient address
                    graph.add((output_uri, ABI.sentToAddress, recipient_uri))
                    
                    # Add script public key if available
                    if tx_output.get("script"):
                        graph.add((output_uri, ABI.scriptPubKey, Literal(tx_output.get("script"), datatype=XSD.string)))
        
        # Add mempool time if available
        if tx_data.get("received"):
            mempool_time = datetime.fromtimestamp(tx_data.get("received"))
            graph.add((tx_uri, ABI.mempoolTime, Literal(mempool_time.isoformat(), datatype=XSD.dateTime)))
    
    def _add_address_to_graph(self, graph: ABIGraph, address: str) -> URIRef:
        """Add a Bitcoin address to the graph and return its URI.
        
        Args:
            graph (ABIGraph): The RDF graph to add to
            address (str): Bitcoin address string
            
        Returns:
            URIRef: URI reference to the Bitcoin address
        """
        address_uri = URIRef(f"http://ontology.naas.ai/abi/addresses/bitcoin/{address}")
        
        # Check if address already exists in graph
        if (address_uri, RDF.type, ABI.BitcoinAddress) not in graph:
            # Determine address type
            if address.startswith("1"):
                graph.add((address_uri, RDF.type, ABI.LegacyAddress))
            elif address.startswith("3"):
                graph.add((address_uri, RDF.type, ABI.SegWitAddress))
            elif address.startswith("bc1"):
                graph.add((address_uri, RDF.type, ABI.Bech32Address))
            else:
                # Default to generic Bitcoin address
                graph.add((address_uri, RDF.type, ABI.BitcoinAddress))
            
            # Add address string
            graph.add((address_uri, ABI.addressString, Literal(address, datatype=XSD.string)))
            
            # Add label
            graph.add((address_uri, RDFS.label, Literal(f"Bitcoin Address {address[:8]}...", datatype=XSD.string)))
        
        return address_uri
    
    def _map_tx_status(self, tx_data: dict) -> URIRef:
        """Map Bitcoin transaction status to ontology status.
        
        Args:
            tx_data (dict): Bitcoin transaction data
            
        Returns:
            URIRef: URI reference to the appropriate status individual
        """
        confirmations = tx_data.get("confirmations", 0)
        if confirmations >= 6:
            return ABI.CompletedStatus
        elif confirmations > 0:
            return ABI.PendingStatus  # Partially confirmed
        elif tx_data.get("double_spend", False):
            return ABI.FailedStatus  # Double spend detected
        else:
            return ABI.PendingStatus  # In mempool but not confirmed 
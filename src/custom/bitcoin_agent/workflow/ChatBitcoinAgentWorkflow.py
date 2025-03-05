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
import random
import os
import datetime
import json
import re
from rdflib import Graph, Literal, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, XSD
from datetime import datetime as dt
from rdflib.plugins.sparql import prepareQuery

# Define namespaces
ABI = Namespace("http://ontology.naas.ai/abi/")

@dataclass
class ChatBitcoinAgentWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for ChatBitcoinAgentWorkflow.
    
    Attributes:
        api_key (str): API key for the Bitcoin blockchain API (optional for simulation)
        network (str): Bitcoin network to use (mainnet or testnet)
        ontology_store_path (str): Base path to store transaction data
    """
    api_key: Optional[str] = None
    network: str = "mainnet"
    ontology_store_path: str = "storage/triplestore/transactions"

class ChatBitcoinAgentWorkflowParameters(WorkflowParameters):
    """Parameters for ChatBitcoinAgentWorkflow execution.
    
    Attributes:
        num_transactions (int): Number of simulated transactions to generate
        min_amount (float): Minimum transaction amount in BTC
        max_amount (float): Maximum transaction amount in BTC
        address_type (str): Type of addresses to generate (legacy, segwit, bech32, or random)
    """
    num_transactions: int = Field(1, description="Number of simulated transactions to generate")
    min_amount: float = Field(0.001, description="Minimum transaction amount in BTC")
    max_amount: float = Field(10.0, description="Maximum transaction amount in BTC")
    address_type: str = Field("random", description="Type of addresses to generate (legacy, segwit, bech32, or random)")

class BalanceQueryParameters(WorkflowParameters):
    """Parameters for querying the account balance.
    
    Attributes:
        None required
    """
    pass

class SparqlQueryParameters(WorkflowParameters):
    """Parameters for executing SPARQL queries on Bitcoin transaction data.
    
    Attributes:
        query (str): The SPARQL query to execute
        timestamp_dir (Optional[str]): Specific timestamp directory to query (defaults to latest)
    """
    query: str = Field(..., description="SPARQL query to execute against Bitcoin transaction data")
    timestamp_dir: Optional[str] = Field(None, description="Specific timestamp directory to query (defaults to latest)")

class NaturalLanguageQueryParameters(WorkflowParameters):
    """Parameters for natural language queries about Bitcoin transactions.
    
    Attributes:
        query (str): The natural language query about transactions or balance
    """
    query: str = Field(..., description="Natural language query about Bitcoin transactions or balance")

class ChatBitcoinAgentWorkflow(Workflow):
    """A workflow for simulating Bitcoin transactions and storing them in a triplestore.
    
    This workflow generates realistic Bitcoin transaction data, converts it to RDF using
    the Bitcoin ontology, and stores it in a timestamped directory.
    """
    __configuration: ChatBitcoinAgentWorkflowConfiguration
    __transactions_history: List[Dict[str, Any]]
    __current_balance: float
    __latest_timestamp_dir: Optional[str]
    
    def __init__(self, configuration: ChatBitcoinAgentWorkflowConfiguration):
        self.__configuration = configuration
        
        # Initialize transactions history and balance
        self.__transactions_history = []
        self.__current_balance = 0.0
        self.__latest_timestamp_dir = None
        
        # Initialize Bitcoin integration with the provided configuration
        integration_config = BitcoinIntegrationConfiguration(
            api_key=self.__configuration.api_key,
            network=self.__configuration.network
        )
        self.__integration = BitcoinIntegration(integration_config)

    def run(self, parameters: ChatBitcoinAgentWorkflowParameters) -> Dict[str, Any]:
        """Generate simulated Bitcoin transactions and store them in a timestamped directory.
        
        Args:
            parameters: Parameters for transaction generation
            
        Returns:
            Dict containing information about the generated transactions and storage location
        """
        # Create timestamp directory
        timestamp = dt.now().strftime("%Y%m%dT%H%M%S")
        storage_dir = os.path.join(self.__configuration.ontology_store_path, timestamp)
        os.makedirs(storage_dir, exist_ok=True)
        
        # Store the latest timestamp directory for SPARQL queries
        self.__latest_timestamp_dir = storage_dir
        
        # Generate simulated transactions
        transactions = self._generate_transactions(parameters)
        
        # Process transactions and convert to RDF
        processed_transactions = []
        combined_graph = Graph()
        
        for tx in transactions:
            # Process the transaction through our own implementation
            graph = self._transaction_to_graph(Graph(), tx)
            
            # Add to combined graph
            for triple in graph:
                combined_graph.add(triple)
            
            # Calculate amount in BTC
            amount_btc = sum([output.get("value", 0) for output in tx.get("outputs", [])]) / 100000000
            
            # Update balance
            self.__current_balance += amount_btc
            
            # Record processed transaction
            tx_info = {
                "hash": tx["hash"],
                "amount": amount_btc,
                "confirmations": tx.get("confirmations", 0),
                "timestamp": timestamp
            }
            processed_transactions.append(tx_info)
            
            # Add to transaction history
            self.__transactions_history.append(tx_info)
            
            # Save individual transaction
            tx_filename = os.path.join(storage_dir, f"{tx['hash']}.ttl")
            with open(tx_filename, "w") as f:
                f.write(graph.serialize(format="turtle"))
        
        # Save combined graph
        combined_filename = os.path.join(storage_dir, "combined.ttl")
        with open(combined_filename, "w") as f:
            f.write(combined_graph.serialize(format="turtle"))
            
        # Save transaction metadata
        metadata = {
            "timestamp": timestamp,
            "num_transactions": len(transactions),
            "transactions": processed_transactions,
            "parameters": {
                "min_amount": parameters.min_amount,
                "max_amount": parameters.max_amount,
                "address_type": parameters.address_type
            },
            "current_balance": self.__current_balance
        }
        
        metadata_filename = os.path.join(storage_dir, "metadata.json")
        with open(metadata_filename, "w") as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "status": "success",
            "timestamp": timestamp,
            "storage_dir": storage_dir,
            "num_transactions": len(transactions),
            "transactions": processed_transactions,
            "current_balance": self.__current_balance
        }
    
    def get_balance(self, parameters: BalanceQueryParameters = None) -> Dict[str, Any]:
        """Get the current account balance and transaction history.
        
        Args:
            parameters: Not used, but required for the workflow interface
            
        Returns:
            Dict containing the current balance and transaction history
        """
        return {
            "current_balance": self.__current_balance,
            "num_transactions": len(self.__transactions_history),
            "transactions": self.__transactions_history[-10:] if len(self.__transactions_history) > 10 else self.__transactions_history,
            "transaction_count": len(self.__transactions_history)
        }

    def _transaction_to_graph(self, graph: Graph, tx_data: dict) -> Graph:
        """Add a Bitcoin transaction to the RDF graph using the Bitcoin ontology.
        
        Args:
            graph (Graph): The RDF graph to add to
            tx_data (dict): Bitcoin transaction data
            
        Returns:
            Graph: The updated RDF graph
        """
        # Add prefixes for clarity
        graph.bind("abi", ABI)
        
        tx_hash = tx_data.get('hash')
        
        # Create transaction URI
        tx_uri = URIRef(f"http://ontology.naas.ai/abi/transactions/bitcoin/{tx_hash}")
        
        # Add transaction type (using the Bitcoin ontology)
        graph.add((tx_uri, RDF.type, ABI.BitcoinTransaction))
        graph.add((tx_uri, RDF.type, ABI.OnChainTransaction))  # All transactions are on-chain
        graph.add((tx_uri, ABI.hasTransactionType, ABI.CashType))
        
        # Add transaction hash
        graph.add((tx_uri, ABI.transactionHash, Literal(tx_hash, datatype=XSD.string)))
        
        # Add transaction properties
        graph.add((tx_uri, RDFS.label, Literal(f"Bitcoin transaction {tx_hash[:8]}...", datatype=XSD.string)))
        graph.add((tx_uri, ABI.description, Literal(f"Bitcoin transaction {tx_hash}", datatype=XSD.string)))
        
        # Add network information
        network_type = ABI.BitcoinMainnet if self.__configuration.network == "mainnet" else ABI.BitcoinTestnet
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
                block_time = dt.fromtimestamp(tx_data.get("confirmed"))
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
            mempool_time = dt.fromtimestamp(tx_data.get("received"))
            graph.add((tx_uri, ABI.mempoolTime, Literal(mempool_time.isoformat(), datatype=XSD.dateTime)))
            
        return graph
    
    def _add_address_to_graph(self, graph: Graph, address: str) -> URIRef:
        """Add a Bitcoin address to the graph and return its URI.
        
        Args:
            graph (Graph): The RDF graph to add to
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

    def _generate_transactions(self, parameters: ChatBitcoinAgentWorkflowParameters) -> List[Dict[str, Any]]:
        """Generate simulated Bitcoin transactions.
        
        Args:
            parameters: Parameters for transaction generation
            
        Returns:
            List of simulated transaction dictionaries
        """
        transactions = []
        
        for i in range(parameters.num_transactions):
            # Generate a random transaction hash
            tx_hash = self._generate_hash()
            
            # Determine number of inputs and outputs
            num_inputs = random.randint(1, 3)
            num_outputs = random.randint(1, 3)
            
            # Generate random amount within the specified range
            amount_satoshis = int(random.uniform(parameters.min_amount, parameters.max_amount) * 100000000)
            
            # Split amount among outputs (keeping some for fee)
            fee = int(amount_satoshis * random.uniform(0.001, 0.01))  # Fee between 0.1% and 1%
            output_values = self._split_amount(amount_satoshis - fee, num_outputs)
            
            # Generate inputs
            inputs = []
            for j in range(num_inputs):
                inputs.append({
                    "addresses": [self._generate_address(parameters.address_type)],
                    "prev_hash": self._generate_hash(),
                    "output_index": random.randint(0, 2),
                    "script": f"scriptSig_{j}_{self._generate_hash()[:16]}"
                })
            
            # Generate outputs
            outputs = []
            for j in range(num_outputs):
                outputs.append({
                    "addresses": [self._generate_address(parameters.address_type)],
                    "value": output_values[j],
                    "script": f"scriptPubKey_{j}_{self._generate_hash()[:16]}"
                })
            
            # Generate block data if confirmed
            confirmations = random.randint(0, 100)
            block_data = {}
            if confirmations > 0:
                block_height = 800000 - random.randint(0, 1000)
                block_hash = self._generate_hash()
                block_time = dt.now() - datetime.timedelta(minutes=confirmations*10)
                
                block_data = {
                    "block_height": block_height,
                    "block_hash": block_hash,
                    "confirmed": int(block_time.timestamp())
                }
            
            # Assemble transaction
            transaction = {
                "hash": tx_hash,
                "inputs": inputs,
                "outputs": outputs,
                "fees": fee,
                "confirmations": confirmations,
                "received": int((dt.now() - datetime.timedelta(minutes=confirmations*10 + random.randint(1, 5))).timestamp()),
                **block_data
            }
            
            transactions.append(transaction)
        
        return transactions
    
    def _generate_hash(self) -> str:
        """Generate a random Bitcoin-like transaction hash.
        
        Returns:
            A 64-character hexadecimal string
        """
        return ''.join(random.choice('0123456789abcdef') for _ in range(64))
    
    def _generate_address(self, address_type: str) -> str:
        """Generate a Bitcoin address of the specified type.
        
        Args:
            address_type: Type of address to generate (legacy, segwit, bech32, or random)
            
        Returns:
            A simulated Bitcoin address
        """
        if address_type == "random":
            address_type = random.choice(["legacy", "segwit", "bech32"])
        
        if address_type == "legacy":
            # Legacy addresses start with 1
            return "1" + ''.join(random.choice('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz') for _ in range(33))
        elif address_type == "segwit":
            # SegWit addresses start with 3
            return "3" + ''.join(random.choice('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz') for _ in range(33))
        elif address_type == "bech32":
            # Bech32 addresses start with bc1
            return "bc1" + ''.join(random.choice('023456789acdefghjklmnpqrstuvwxyz') for _ in range(39))
        else:
            # Default to legacy
            return "1" + ''.join(random.choice('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz') for _ in range(33))
    
    def _split_amount(self, total: int, parts: int) -> List[int]:
        """Split a total amount into a specified number of random parts.
        
        Args:
            total: Total amount to split
            parts: Number of parts to split into
            
        Returns:
            List of split amounts
        """
        if parts <= 1:
            return [total]
        
        # Generate random points
        points = sorted([random.randint(1, total - 1) for _ in range(parts - 1)])
        
        # Calculate split amounts
        result = [points[0]]
        for i in range(1, len(points)):
            result.append(points[i] - points[i-1])
        result.append(total - points[-1])
        
        return result

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="simulate_bitcoin_transactions",
                description="Generates simulated Bitcoin transactions and stores them in a triplestore",
                func=lambda **kwargs: self.run(ChatBitcoinAgentWorkflowParameters(**kwargs)),
                args_schema=ChatBitcoinAgentWorkflowParameters
            ),
            StructuredTool(
                name="get_bitcoin_balance",
                description="Retrieves the current Bitcoin account balance and transaction history",
                func=lambda **kwargs: self.get_balance(BalanceQueryParameters(**kwargs) if kwargs else BalanceQueryParameters()),
                args_schema=BalanceQueryParameters
            ),
            StructuredTool(
                name="execute_sparql_query",
                description="Executes a SPARQL query on the Bitcoin transaction data stored in RDF format",
                func=lambda **kwargs: self.execute_sparql_query(SparqlQueryParameters(**kwargs)),
                args_schema=SparqlQueryParameters
            ),
            StructuredTool(
                name="query_bitcoin_data",
                description="Query Bitcoin transaction data using natural language (e.g., 'What are the 5 latest transactions?', 'What's my current balance?')",
                func=lambda **kwargs: self.natural_language_query(NaturalLanguageQueryParameters(**kwargs)),
                args_schema=NaturalLanguageQueryParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/simulate-bitcoin-transactions")
        def simulate_transactions(parameters: ChatBitcoinAgentWorkflowParameters):
            return self.run(parameters)

    def execute_sparql_query(self, parameters: SparqlQueryParameters) -> Dict[str, Any]:
        """Execute a SPARQL query on Bitcoin transaction data.
        
        Args:
            parameters: The SPARQL query and optional timestamp directory
            
        Returns:
            Dict containing the query results
        """
        # Determine which directory to use for the query
        if parameters.timestamp_dir:
            # Use the specified directory
            query_dir = os.path.join(self.__configuration.ontology_store_path, parameters.timestamp_dir)
        elif self.__latest_timestamp_dir:
            # Use the latest directory where we stored transactions
            query_dir = self.__latest_timestamp_dir
        else:
            # Try to find the latest directory in storage_path
            try:
                all_dirs = [os.path.join(self.__configuration.ontology_store_path, d) 
                           for d in os.listdir(self.__configuration.ontology_store_path)
                           if os.path.isdir(os.path.join(self.__configuration.ontology_store_path, d))]
                if all_dirs:
                    query_dir = max(all_dirs, key=os.path.getmtime)
                else:
                    return {"error": "No transaction directories found"}
            except (FileNotFoundError, ValueError):
                return {"error": "No transaction directories found"}
        
        # Check if combined.ttl exists in the directory
        combined_ttl_path = os.path.join(query_dir, "combined.ttl")
        if not os.path.exists(combined_ttl_path):
            return {"error": f"No combined.ttl file found in {query_dir}"}
        
        # Load the graph
        g = Graph()
        g.parse(combined_ttl_path, format="turtle")
        
        # Prepare namespaces
        g.bind("abi", ABI)
        g.bind("rdf", RDF)
        g.bind("rdfs", RDFS)
        g.bind("xsd", XSD)
        
        # Execute the SPARQL query
        try:
            # Prepare the query
            query = prepareQuery(parameters.query, 
                                initNs={"abi": ABI, 
                                        "rdf": RDF, 
                                        "rdfs": RDFS, 
                                        "xsd": XSD})
            
            # Execute the query
            results = g.query(query)
            
            # Format the results
            formatted_results = []
            for row in results:
                result_row = {}
                for i, var in enumerate(results.vars):
                    value = row[i]
                    if value is None:
                        result_row[var] = None
                    elif isinstance(value, URIRef):
                        result_row[var] = str(value)
                    elif isinstance(value, Literal):
                        result_row[var] = value.value
                    else:
                        result_row[var] = str(value)
                formatted_results.append(result_row)
            
            return {
                "status": "success",
                "query": parameters.query,
                "results": formatted_results,
                "result_count": len(formatted_results),
                "directory": query_dir
            }
            
        except Exception as e:
            return {
                "status": "error",
                "query": parameters.query,
                "error": str(e)
            }

    def natural_language_query(self, parameters: NaturalLanguageQueryParameters) -> Dict[str, Any]:
        """Process natural language queries about Bitcoin transactions and balances.
        
        This method understands common questions about:
        - Account balance and position
        - Recent transactions
        - Largest/smallest transactions
        - Transactions by status
        - Transactions by amount range
        - Current Bitcoin price
        - Bitcoin price charts
        
        Args:
            parameters: Natural language query
            
        Returns:
            Dict containing the query results
        """
        query = parameters.query.lower().strip()
        
        # Check if this is a chart query
        if any(term in query for term in ["chart", "graph", "plot", "visualization", "figure"]):
            # Look for specific time period
            if any(pattern in query for pattern in ["7 day", "week", "7-day", "7d"]):
                from src.bitcoin.analytics import generate_price_history_chart
                return generate_price_history_chart(days=7)
            elif any(pattern in query for pattern in ["30 day", "month", "30-day", "30d"]):
                from src.bitcoin.analytics import generate_price_history_chart
                return generate_price_history_chart(days=30)
            elif any(pattern in query for pattern in ["90 day", "3 month", "quarter", "90-day", "90d"]):
                from src.bitcoin.analytics import generate_price_history_chart
                return generate_price_history_chart(days=90)
            elif any(pattern in query for pattern in ["year", "365 day", "12 month", "365-day", "365d", "1y"]):
                from src.bitcoin.analytics import generate_price_history_chart
                return generate_price_history_chart(days=365)
            else:
                # Default to 24-hour chart
                from src.bitcoin.analytics import generate_price_chart
                return generate_price_chart()
        
        # Check if this is a price query
        if any(term in query for term in ["price", "worth", "value", "cost", "rate", "exchange"]):
            # This is a price query, use the Bitcoin integration to get the current price
            return self.__integration.get_bitcoin_price()
        
        # Check if this is a balance query
        if any(term in query for term in ["balance", "position", "account", "total", "sum"]):
            # This is a balance query, use the get_balance method
            return self.get_balance()
        
        # Check if this is a query for recent transactions
        if any(term in query for term in ["recent", "latest", "last", "new"]):
            # Extract the number if specified
            num_match = re.search(r'(\d+)', query)
            limit = int(num_match.group(1)) if num_match else 10
            
            # Create a SPARQL query for the latest transactions
            sparql_query = f"""
            SELECT ?tx ?hash ?amount ?time
            WHERE {{
                ?tx rdf:type abi:BitcoinTransaction ;
                   abi:transactionHash ?hash ;
                   abi:amount ?amount .
                OPTIONAL {{ ?tx abi:mempoolTime ?time }}
            }}
            ORDER BY DESC(?time)
            LIMIT {limit}
            """
            
            # Execute the SPARQL query
            return self.execute_sparql_query(SparqlQueryParameters(query=sparql_query))
        
        # Check if this is a query for largest/smallest transactions
        if any(term in query for term in ["largest", "biggest", "highest", "most expensive"]):
            # Extract the number if specified
            num_match = re.search(r'(\d+)', query)
            limit = int(num_match.group(1)) if num_match else 5
            
            # Create a SPARQL query for the largest transactions
            sparql_query = f"""
            SELECT ?tx ?hash ?amount
            WHERE {{
                ?tx rdf:type abi:BitcoinTransaction ;
                   abi:transactionHash ?hash ;
                   abi:amount ?amount .
            }}
            ORDER BY DESC(?amount)
            LIMIT {limit}
            """
            
            # Execute the SPARQL query
            return self.execute_sparql_query(SparqlQueryParameters(query=sparql_query))
        
        if any(term in query for term in ["smallest", "lowest", "least expensive"]):
            # Extract the number if specified
            num_match = re.search(r'(\d+)', query)
            limit = int(num_match.group(1)) if num_match else 5
            
            # Create a SPARQL query for the smallest transactions
            sparql_query = f"""
            SELECT ?tx ?hash ?amount
            WHERE {{
                ?tx rdf:type abi:BitcoinTransaction ;
                   abi:transactionHash ?hash ;
                   abi:amount ?amount .
            }}
            ORDER BY ASC(?amount)
            LIMIT {limit}
            """
            
            # Execute the SPARQL query
            return self.execute_sparql_query(SparqlQueryParameters(query=sparql_query))
        
        # Check if this is a query for transactions by status
        if any(term in query for term in ["completed", "pending", "failed", "status"]):
            # Determine the status to filter by
            status = None
            if "completed" in query or "confirmed" in query:
                status = "CompletedStatus"
            elif "pending" in query:
                status = "PendingStatus"
            elif "failed" in query:
                status = "FailedStatus"
            
            # Create a SPARQL query for transactions by status
            if status:
                sparql_query = f"""
                SELECT ?tx ?hash ?amount ?confirmations
                WHERE {{
                    ?tx rdf:type abi:BitcoinTransaction ;
                       abi:transactionHash ?hash ;
                       abi:amount ?amount ;
                       abi:hasStatus abi:{status} ;
                       abi:confirmations ?confirmations .
                }}
                ORDER BY DESC(?confirmations)
                LIMIT 10
                """
            else:
                # Query for all statuses with counts
                sparql_query = """
                SELECT ?status (COUNT(?tx) as ?count)
                WHERE {
                    ?tx rdf:type abi:BitcoinTransaction ;
                       abi:hasStatus ?status .
                }
                GROUP BY ?status
                """
            
            # Execute the SPARQL query
            return self.execute_sparql_query(SparqlQueryParameters(query=sparql_query))
        
        # Check if this is a query for transactions by amount range
        if "more than" in query or "greater than" in query or "over" in query:
            # Extract the amount threshold
            amount_match = re.search(r'(\d+(\.\d+)?)', query)
            amount = float(amount_match.group(1)) if amount_match else 1.0
            
            # Create a SPARQL query for transactions over a certain amount
            sparql_query = f"""
            SELECT ?tx ?hash ?amount
            WHERE {{
                ?tx rdf:type abi:BitcoinTransaction ;
                   abi:transactionHash ?hash ;
                   abi:amount ?amount .
                FILTER(?amount > {amount})
            }}
            ORDER BY DESC(?amount)
            LIMIT 10
            """
            
            # Execute the SPARQL query
            return self.execute_sparql_query(SparqlQueryParameters(query=sparql_query))
        
        if "less than" in query or "smaller than" in query or "under" in query:
            # Extract the amount threshold
            amount_match = re.search(r'(\d+(\.\d+)?)', query)
            amount = float(amount_match.group(1)) if amount_match else 1.0
            
            # Create a SPARQL query for transactions under a certain amount
            sparql_query = f"""
            SELECT ?tx ?hash ?amount
            WHERE {{
                ?tx rdf:type abi:BitcoinTransaction ;
                   abi:transactionHash ?hash ;
                   abi:amount ?amount .
                FILTER(?amount < {amount})
            }}
            ORDER BY ASC(?amount)
            LIMIT 10
            """
            
            # Execute the SPARQL query
            return self.execute_sparql_query(SparqlQueryParameters(query=sparql_query))
        
        # If we couldn't identify a specific query type, fall back to a general transaction query
        sparql_query = """
        SELECT ?tx ?hash ?amount ?status
        WHERE {
            ?tx rdf:type abi:BitcoinTransaction ;
               abi:transactionHash ?hash ;
               abi:amount ?amount ;
               abi:hasStatus ?status .
        }
        LIMIT 10
        """
        
        return self.execute_sparql_query(SparqlQueryParameters(query=sparql_query)) 
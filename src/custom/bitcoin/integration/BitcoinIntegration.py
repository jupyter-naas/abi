from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import requests
import json
from datetime import datetime
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

LOGO_URL = "https://logo.clearbit.com/bitcoin.org"

@dataclass
class BitcoinIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Bitcoin integration.
    
    Attributes:
        api_key (str): API key for the Bitcoin blockchain service (e.g., BlockCypher, Blockchain.info)
        api_secret (Optional[str]): API secret for the service if required
        node_url (Optional[str]): URL of a Bitcoin node if using direct connection
        base_url (str): Base URL for the Bitcoin API service. Defaults to BlockCypher's API
        network (str): Bitcoin network to use (mainnet, testnet). Defaults to "mainnet"
    """
    api_key: str
    api_secret: Optional[str] = None
    node_url: Optional[str] = None
    base_url: str = "https://api.blockcypher.com/v1"
    network: str = "mainnet"

class BitcoinIntegration(Integration):
    """Bitcoin blockchain integration client.
    
    This integration provides methods to interact with the Bitcoin blockchain,
    including retrieving transaction data, wallet information, and blockchain status.
    
    Attributes:
        __configuration (BitcoinIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    
    Example:
        >>> config = BitcoinIntegrationConfiguration(
        ...     api_key="your_api_key"
        ... )
        >>> integration = BitcoinIntegration(config)
    """

    __configuration: BitcoinIntegrationConfiguration

    def __init__(self, configuration: BitcoinIntegrationConfiguration):
        """Initialize Bitcoin client with credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        # Select the appropriate Bitcoin network endpoint
        if self.__configuration.network == "mainnet":
            self.chain = "btc/main"
        else:
            self.chain = "btc/test3"
        
        self.headers = {
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None, data: Dict = None) -> Dict:
        """Make HTTP request to Bitcoin API.
        
        Args:
            endpoint (str): API endpoint
            method (str): HTTP method (GET, POST, etc.). Defaults to "GET"
            params (Dict, optional): Query parameters. Defaults to None.
            data (Dict, optional): Request body for POST requests. Defaults to None.
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}/{self.chain}{endpoint}"
        
        if params is None:
            params = {}
        
        # Add API key to all requests
        if self.__configuration.api_key:
            params["token"] = self.__configuration.api_key
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Bitcoin API request failed: {str(e)}")

    def get_blockchain_info(self) -> Dict:
        """Get current Bitcoin blockchain information.
        
        Returns:
            Dict: Blockchain information including current height, hash rate, etc.
        """
        return self._make_request("")
    
    def get_block_by_height(self, height: int) -> Dict:
        """Get block information by block height.
        
        Args:
            height (int): Block height
            
        Returns:
            Dict: Block information
        """
        return self._make_request(f"/blocks/{height}")
    
    def get_block_by_hash(self, block_hash: str) -> Dict:
        """Get block information by block hash.
        
        Args:
            block_hash (str): Block hash
            
        Returns:
            Dict: Block information
        """
        return self._make_request(f"/blocks/{block_hash}")

    def get_transaction(self, tx_hash: str, include_confirmations: bool = True) -> Dict:
        """Get transaction information by transaction hash.
        
        Args:
            tx_hash (str): Transaction hash
            include_confirmations (bool): Whether to include confirmation count
            
        Returns:
            Dict: Transaction information
        """
        params = {
            "includeConfidence": "true" if include_confirmations else "false"
        }
        return self._make_request(f"/txs/{tx_hash}", params=params)

    def get_address_info(self, address: str, include_txs: bool = False, limit: int = 50) -> Dict:
        """Get information about a Bitcoin address.
        
        Args:
            address (str): Bitcoin address
            include_txs (bool): Include transactions in the response
            limit (int): Maximum number of transactions to return if include_txs is True
            
        Returns:
            Dict: Address information including balance, transactions, etc.
        """
        params = {}
        if include_txs:
            params["includeScript"] = "true"
            params["limit"] = limit
        
        return self._make_request(f"/addrs/{address}", params=params)
    
    def list_address_transactions(self, address: str, limit: int = 50, before_height: Optional[int] = None) -> List[Dict]:
        """Get list of transactions for a Bitcoin address.
        
        Args:
            address (str): Bitcoin address
            limit (int): Maximum number of transactions to return
            before_height (int, optional): Only return transactions before this block height
            
        Returns:
            List[Dict]: List of transactions for the address
        """
        params = {
            "limit": limit
        }
        
        if before_height:
            params["before"] = before_height
        
        response = self._make_request(f"/addrs/{address}/txs", params=params)
        return response.get("txs", [])
    
    def create_wallet(self, name: str) -> Dict:
        """Create a new Bitcoin wallet.
        
        Args:
            name (str): Wallet name
            
        Returns:
            Dict: New wallet information including addresses
        """
        data = {
            "name": name,
            "generate_wif": True
        }
        return self._make_request("/wallets", method="POST", data=data)
    
    def get_wallet_transactions(self, wallet_name: str, limit: int = 50) -> List[Dict]:
        """Get list of transactions for a wallet.
        
        Args:
            wallet_name (str): Wallet name or ID
            limit (int): Maximum number of transactions to return
            
        Returns:
            List[Dict]: List of transactions for the wallet
        """
        params = {
            "limit": limit
        }
        
        response = self._make_request(f"/wallets/{wallet_name}/txs", params=params)
        return response.get("txs", [])
    
    def get_bitcoin_price(self) -> Dict:
        """Get the current Bitcoin price information.
        
        This method fetches the current Bitcoin price from multiple exchanges
        along with market data like 24h change, volume, etc.
        
        Returns:
            Dict: Current Bitcoin price and market information
        """
        # For the BlockCypher API, we need to use a different endpoint
        # that gives us market rates
        try:
            # First attempt: Use the exchange rates API
            url = f"{self.__configuration.base_url}/exchange/rates"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Find the BTC-USD rate
            for rate in data:
                if rate.get("code") == "USD":
                    return {
                        "price_usd": rate.get("rate", 0),
                        "source": "BlockCypher",
                        "timestamp": datetime.now().isoformat(),
                        "currency": "USD",
                        "success": True
                    }
            
            # Fallback to another approach if not found
            raise Exception("USD rate not found in BlockCypher response")
            
        except Exception as e:
            # Second attempt: Use the CoinGecko API which has better price data
            try:
                url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,eur&include_market_cap=true&include_24hr_vol=true&include_24hr_change=true&include_last_updated_at=true"
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                
                bitcoin_data = data.get("bitcoin", {})
                return {
                    "price_usd": bitcoin_data.get("usd", 0),
                    "price_eur": bitcoin_data.get("eur", 0),
                    "market_cap_usd": bitcoin_data.get("usd_market_cap", 0),
                    "volume_24h_usd": bitcoin_data.get("usd_24h_vol", 0),
                    "change_24h_percent": bitcoin_data.get("usd_24h_change", 0),
                    "last_updated": datetime.fromtimestamp(bitcoin_data.get("last_updated_at", 0)).isoformat(),
                    "source": "CoinGecko",
                    "success": True
                }
                
            except Exception as coingecko_error:
                # Final fallback: If all APIs fail, return an error
                return {
                    "success": False,
                    "error": f"Failed to fetch Bitcoin price: {str(e)}. CoinGecko fallback also failed: {str(coingecko_error)}"
                }
    
    def map_to_transaction_ontology(self, tx_data: Dict) -> Dict:
        """Maps Bitcoin transaction data to the ABI Transaction ontology format.
        
        This method converts Bitcoin-specific transaction data into the standardized
        Transaction ontology format used by ABI.
        
        Args:
            tx_data (Dict): Bitcoin transaction data
            
        Returns:
            Dict: Transaction data in ABI ontology format
        """
        # Create a mapping to our ontology
        transaction = {
            "type": "CashTransaction",
            "transactionType": "CashType",
            "id": tx_data.get("hash"),
            "description": f"Bitcoin transaction {tx_data.get('hash', 'unknown')}",
            "amount": sum([output.get("value", 0) / 100000000 for output in tx_data.get("outputs", [])]),
            "currency": "BTC",
            "timestamp": datetime.fromtimestamp(tx_data.get("received", datetime.now().timestamp())).isoformat(),
            "status": self._map_status(tx_data),
            "senders": [input.get("addresses", [None])[0] for input in tx_data.get("inputs", []) if "addresses" in input],
            "recipients": [output.get("addresses", [None])[0] for output in tx_data.get("outputs", []) if "addresses" in output],
            "confirmations": tx_data.get("confirmations", 0),
            "blockHeight": tx_data.get("block_height"),
            "blockHash": tx_data.get("block_hash"),
            "fees": tx_data.get("fees", 0) / 100000000,
        }
        
        return transaction
    
    def _map_status(self, tx_data: Dict) -> str:
        """Maps Bitcoin transaction status to ontology status.
        
        Args:
            tx_data (Dict): Bitcoin transaction data
            
        Returns:
            str: Status matching the Transaction ontology (PendingStatus, CompletedStatus, FailedStatus)
        """
        confirmations = tx_data.get("confirmations", 0)
        if confirmations >= 6:
            return "CompletedStatus"
        elif confirmations > 0:
            return "PendingStatus"  # Partially confirmed
        elif tx_data.get("double_spend", False):
            return "FailedStatus"  # Double spend detected
        else:
            return "PendingStatus"  # In mempool but not confirmed 

def as_tools(configuration: BitcoinIntegrationConfiguration):
    """Convert Bitcoin integration into LangChain tools."""
    integration = BitcoinIntegration(configuration)
    
    class TransactionHashSchema(BaseModel):
        tx_hash: str = Field(..., description="Bitcoin transaction hash")
        include_confirmations: bool = Field(True, description="Whether to include confirmation count")
    
    class AddressInfoSchema(BaseModel):
        address: str = Field(..., description="Bitcoin address")
        include_txs: bool = Field(False, description="Include transactions in the response")
        limit: int = Field(50, description="Maximum number of transactions to return if include_txs is True")
    
    class AddressTransactionsSchema(BaseModel):
        address: str = Field(..., description="Bitcoin address")
        limit: int = Field(50, description="Maximum number of transactions to return")
        before_height: Optional[int] = Field(None, description="Only return transactions before this block height")
    
    class BlockInfoSchema(BaseModel):
        height: int = Field(..., description="Block height")
    
    class BlockHashSchema(BaseModel):
        block_hash: str = Field(..., description="Block hash")
    
    class BlockchainInfoSchema(BaseModel):
        pass  # No parameters needed, but schema must be provided
    
    class BitcoinPriceSchema(BaseModel):
        pass  # No parameters needed, but schema must be provided
    
    return [
        StructuredTool(
            name="bitcoin_get_transaction",
            description="Get detailed information about a Bitcoin transaction by its hash.",
            func=lambda tx_hash, include_confirmations=True: integration.get_transaction(tx_hash, include_confirmations),
            args_schema=TransactionHashSchema
        ),
        StructuredTool(
            name="bitcoin_get_address_info",
            description="Get information about a Bitcoin address including balance and optional transaction history.",
            func=lambda address, include_txs=False, limit=50: integration.get_address_info(address, include_txs, limit),
            args_schema=AddressInfoSchema
        ),
        StructuredTool(
            name="bitcoin_list_address_transactions",
            description="Get list of transactions for a Bitcoin address.",
            func=lambda address, limit=50, before_height=None: integration.list_address_transactions(address, limit, before_height),
            args_schema=AddressTransactionsSchema
        ),
        StructuredTool(
            name="bitcoin_get_block_by_height",
            description="Get block information by block height.",
            func=lambda height: integration.get_block_by_height(height),
            args_schema=BlockInfoSchema
        ),
        StructuredTool(
            name="bitcoin_get_block_by_hash",
            description="Get block information by block hash.",
            func=lambda block_hash: integration.get_block_by_hash(block_hash),
            args_schema=BlockHashSchema
        ),
        StructuredTool(
            name="bitcoin_get_blockchain_info",
            description="Get current Bitcoin blockchain information including height, hash rate, etc.",
            func=lambda: integration.get_blockchain_info(),
            args_schema=BlockchainInfoSchema
        ),
        StructuredTool(
            name="bitcoin_get_current_price",
            description="Get the current Bitcoin price in USD and EUR with market data.",
            func=lambda: integration.get_bitcoin_price(),
            args_schema=BitcoinPriceSchema
        )
    ] 
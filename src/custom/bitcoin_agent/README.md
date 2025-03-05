# Bitcoin Module

This module provides Bitcoin-related functionality for the ABI platform, including:

- Bitcoin transaction simulation
- Bitcoin price data and charts
- Natural language and SPARQL query processing for Bitcoin data
- Integration with Bitcoin blockchain data

## Directory Structure

```
/src/custom/bitcoin_agent/
├── agent/              # Bitcoin agent implementation
├── analytics/          # Bitcoin price analytics and charts
├── integration/        # Bitcoin blockchain integration 
├── models/             # Model provider for Bitcoin NLP
├── pipeline/           # Data pipelines for Bitcoin transactions
├── tests/              # Testing and validation tools
└── workflow/           # Bitcoin agent workflows
```

## Usage Examples

### Bitcoin Agent

```python
from src.custom.bitcoin_agent.agent import create_bitcoin_agent
from src.custom.bitcoin_agent.models import ModelConfig, ModelProvider

# Create a Bitcoin agent with default settings
agent = create_bitcoin_agent()

# Create a Bitcoin agent with a custom model
model_config = ModelConfig(
    provider=ModelProvider.OPENAI,
    model_name="gpt-4",
    temperature=0.7
)
agent = create_bitcoin_agent(model_config=model_config)

# Run the agent
response = agent.invoke("What's the current Bitcoin price?")
```

### Transaction Simulation

```python
from src.custom.bitcoin_agent.integration import BitcoinIntegration, BitcoinIntegrationConfiguration

# Create a Bitcoin integration
config = BitcoinIntegrationConfiguration(
    api_key="your_api_key",
    network="mainnet"
)
integration = BitcoinIntegration(config)

# Generate a simulated transaction
transaction = integration.generate_simulated_transaction(
    amount=1.5,
    direction="outgoing"
)

# Generate a batch of transactions
transactions = integration.generate_simulated_transaction_batch(
    count=10,
    min_amount=0.1,
    max_amount=10.0
)
```

### Natural Language Queries

```python
from src.custom.bitcoin_agent.workflow import ChatBitcoinAgentWorkflow, ChatBitcoinAgentWorkflowConfiguration
from src.custom.bitcoin_agent.integration import BitcoinIntegration, BitcoinIntegrationConfiguration

# Setup the workflow
integration = BitcoinIntegration(BitcoinIntegrationConfiguration())
workflow = ChatBitcoinAgentWorkflow(ChatBitcoinAgentWorkflowConfiguration(
    integration=integration
))

# Process natural language queries
result = workflow.natural_language_query("What are my 5 largest transactions?")
result = workflow.natural_language_query("How many pending transactions do I have?")
result = workflow.natural_language_query("What's the current Bitcoin price?")
```

### SPARQL Queries

```python
from src.custom.bitcoin_agent.workflow import ChatBitcoinAgentWorkflow, ChatBitcoinAgentWorkflowConfiguration
from src.custom.bitcoin_agent.integration import BitcoinIntegration, BitcoinIntegrationConfiguration

# Setup the workflow
integration = BitcoinIntegration(BitcoinIntegrationConfiguration())
workflow = ChatBitcoinAgentWorkflow(ChatBitcoinAgentWorkflowConfiguration(
    integration=integration
))

# Execute a SPARQL query
sparql_query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX btc: <http://ontology.naas.ai/abi/bitcoin#>

SELECT ?tx ?amount ?timestamp 
WHERE {
  ?tx rdf:type btc:Transaction ;
      btc:amount ?amount ;
      btc:timestamp ?timestamp .
  FILTER(?amount > 1.0)
}
ORDER BY DESC(?amount)
LIMIT 5
"""
result = workflow.execute_sparql(sparql_query)
```

### Price Queries and Charts

```python
from src.custom.bitcoin_agent.analytics import generate_price_chart, generate_price_history_chart

# Generate a 24-hour price chart
price_data = generate_price_chart(save_path="bitcoin_price_24h.png")

# Generate a 30-day price history chart
history_data = generate_price_history_chart(
    days=30,
    vs_currency="usd",
    save_path="bitcoin_price_30d.png"
)
```

## Testing and Validation Framework

The Bitcoin module includes a robust testing framework to ensure price accuracy and reliability:

### Price Validation Tests

#### Single Source Validation
```bash
make test-bitcoin-price
```

This test:
- Creates a Bitcoin agent and asks it for the current price
- Fetches the actual Bitcoin price from external sources (Yahoo Finance with CoinGecko fallback)
- Calculates the difference and validates it's within tolerance (default 5%)
- Saves test results to a timestamped JSON file in `storage/tests/bitcoin_price_validation/`

Sample output:
```
Bitcoin Price Validation Test
-----------------------------
Creating Bitcoin agent...
Querying current price...
Validating price against real-time data...
Price from CoinGecko: $93,936.00 USD
Agent reported price: $94,077.00 USD
Difference: $141.00 (0.15%)
Tolerance: 5.00%
Result: ✅ PASS - Price is within acceptable tolerance
```

#### Consensus Validation
```bash
make test-bitcoin-consensus
```

This test:
- Queries multiple price providers (CoinGecko, Yahoo Finance, etc.)
- Calculates a consensus price (average) with statistical measures
- Validates the agent's price against this consensus
- Provides more robust validation against market fluctuations

Sample output:
```
Bitcoin Price Providers Consensus Test
-------------------------------------
CoinGecko price: $93,936.00 USD
Consensus price: $93,936.00 USD
Standard deviation: $0.00
Agent reported price: $94,077.00 USD
Difference: $141.00 (0.15%)
Tolerance: 5.00%
Result: ✅ PASS - Price matches consensus
```

### Error Handling

The validation framework includes robust error handling:
- Automatically falls back to alternative data sources if primary source fails
- Continues testing even if one provider is unavailable
- Provides clear error messages when API issues occur

### Programmatic Testing

You can also run validation tests programmatically:

```python
from src.custom.bitcoin_agent.tests.test_price_validation import validate_bitcoin_price
from src.custom.bitcoin_agent.tests.test_price_providers import validate_agent_against_consensus
from src.custom.bitcoin_agent.agent import create_bitcoin_agent

# Create agent and get price response
agent = create_bitcoin_agent()
response = agent.invoke("What is the current Bitcoin price?")

# Validate against a single source
result = validate_bitcoin_price(response)
print(f"Within tolerance: {result.is_within_tolerance}")

# Validate against consensus
consensus_result = validate_agent_against_consensus(response)
print(f"Within consensus tolerance: {consensus_result.is_within_tolerance}")
```

## Bitcoin Agent Capabilities

The Bitcoin agent supports a wide range of queries and functionality:

### Price Information

| Example Question | Response |
|-----------------|-------------------|
| "What is the current Bitcoin price?" | Current price with timestamp |
| "How much has Bitcoin changed today?" | Price change with percentage |
| "Convert 2.5 BTC to USD" | Conversion with current exchange rate |
| "Show me a price chart for the last month" | Generates and displays a chart |

### Transaction Analysis

| Example Question | Response |
|-----------------|-------------------|
| "Explain transaction [hash]" | Transaction details and interpretation |
| "Show recent transactions for [address]" | List of recent transactions |
| "What's my wallet balance?" | Current balance information |
| "Generate 10 simulated transactions" | Creates and stores simulated data |

### Blockchain Information

| Example Question | Response |
|-----------------|-------------------|
| "What's in block #800000?" | Block details including transactions |
| "How many confirmations does [tx] have?" | Confirmation count and status |
| "What are current network fees?" | Fee estimates and recommendations |
| "Show mempool statistics" | Current mempool size and pending tx count |

### Educational Content

| Example Question | Response |
|-----------------|-------------------|
| "Explain Bitcoin mining" | Educational explanation of the process |
| "What is a SegWit address?" | Technical explanation with examples |
| "How does the Lightning Network work?" | Description of Layer 2 solution |
| "Compare Bitcoin and Ethereum" | Comparative analysis |

### Advanced Analysis

| Example Question | Response |
|-----------------|-------------------|
| "Run SPARQL [query]" | Executes query against transaction data |
| "Analyze price correlation with S&P 500" | Statistical correlation analysis |
| "Show distribution of my transaction amounts" | Statistical analysis with visualization |
| "Predict Bitcoin price trend" | Trend analysis based on historical data | 
# DPROD Technical Architecture

## Architecture Overview

The DPROD implementation in ABI follows a **layered architecture** that integrates seamlessly with existing components while adding semantic data management capabilities. The design emphasizes modularity, performance, and standards compliance.

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          ABI Core System                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   AbiAgent      │  │  Local Agents   │  │  Cloud Agents   │ │
│  │   (Enhanced)    │  │ (Qwen,DeepSeek, │  │ (ChatGPT,Claude,│ │
│  │                 │  │  Gemma)         │  │  Grok, etc.)    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                     DPROD Integration Layer                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Agent Registry  │  │ Lineage Tracker │  │ Observability   │ │
│  │ Service         │  │                 │  │ Framework       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                      Data & Query Layer                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ RDF Triple      │  │ SPARQL Query    │  │ Metrics Store   │ │
│  │ Store           │  │ Engine          │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                     External Integrations                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Data Catalogs   │  │ Enterprise APIs │  │ Monitoring      │ │
│  │ (DataHub, etc.) │  │                 │  │ Systems         │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. DPROD Ontology Extension

**Location**: `src/core/modules/ontology/dprod/`

```python
# src/core/modules/ontology/dprod/models/DPRODDataProduct.py
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class DPRODDataProduct:
    """DPROD-compliant data product representation of an AI agent."""
    
    # Core DPROD properties
    id: str                              # URI identifier
    type: str = "DataProduct"            # DPROD type
    label: str                          # Human-readable name
    description: str                    # Agent description
    
    # Ports (DPROD core concept)
    input_ports: List['DPRODDataService']  # User prompts, context
    output_ports: List['DPRODDataService'] # Agent responses
    observability_port: Optional['DPRODDataService'] = None
    
    # Agent-specific metadata
    capabilities: List[str]             # ["coding", "reasoning", "multilingual"]
    model_info: Dict[str, Any]          # Model type, parameters, etc.
    performance_tier: str               # "high", "medium", "low"
    privacy_level: str                  # "local", "cloud", "hybrid"
    
    # DPROD compliance
    conforms_to: str                    # Schema URI
    created_at: datetime
    modified_at: datetime
    version: str = "1.0"
    
    def to_jsonld(self) -> Dict[str, Any]:
        """Convert to JSON-LD format for RDF storage."""
        return {
            "@context": "https://ekgf.github.io/dprod/dprod.jsonld",
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "description": self.description,
            "inputPort": [port.to_jsonld() for port in self.input_ports],
            "outputPort": [port.to_jsonld() for port in self.output_ports],
            "observabilityPort": self.observability_port.to_jsonld() if self.observability_port else None,
            "abi:capabilities": self.capabilities,
            "abi:modelInfo": self.model_info,
            "abi:performanceTier": self.performance_tier,
            "abi:privacyLevel": self.privacy_level,
            "dcat:conformsTo": self.conforms_to,
            "dcterms:created": self.created_at.isoformat(),
            "dcterms:modified": self.modified_at.isoformat(),
            "owl:versionInfo": self.version
        }

@dataclass  
class DPRODDataService:
    """DPROD data service representing agent input/output ports."""
    
    id: str
    type: str = "DataService"
    label: str
    endpoint_url: Optional[str] = None
    
    # Distribution information
    access_service_of: 'DPRODDistribution'
    
    def to_jsonld(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "endpointURL": self.endpoint_url,
            "isAccessServiceOf": self.access_service_of.to_jsonld()
        }

@dataclass
class DPRODDistribution:
    """DPROD distribution representing data format and schema."""
    
    type: str = "Distribution"
    format: str                         # MIME type
    is_distribution_of: 'DPRODDataset'
    
    def to_jsonld(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "format": self.format,
            "isDistributionOf": self.is_distribution_of.to_jsonld()
        }

@dataclass
class DPRODDataset:
    """DPROD dataset representing the actual data."""
    
    id: str
    type: str = "Dataset" 
    label: Optional[str] = None
    conforms_to: str                    # Schema URI
    
    def to_jsonld(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "conformsTo": self.conforms_to
        }
```

### 2. Agent Registration System

**Location**: `src/core/modules/dprod/services/`

```python
# src/core/modules/dprod/services/AgentRegistryService.py
from typing import Dict, List, Optional
from ..models.DPRODDataProduct import DPRODDataProduct, DPRODDataService, DPRODDistribution, DPRODDataset
from ..storage.DPRODTripleStore import DPRODTripleStore

class AgentRegistryService:
    """Service for registering agents as DPROD-compliant data products."""
    
    def __init__(self, triple_store: DPRODTripleStore):
        self.triple_store = triple_store
        self.base_uri = "https://abi.naas.ai"
        
    def register_agent(self, agent_name: str, agent_config: Dict) -> DPRODDataProduct:
        """Register an AI agent as a DPROD data product."""
        
        # Generate URIs
        agent_uri = f"{self.base_uri}/data-product/{agent_name.lower()}"
        input_port_uri = f"{agent_uri}/input"
        output_port_uri = f"{agent_uri}/output" 
        observability_port_uri = f"{agent_uri}/observability"
        
        # Create input port (user prompts)
        input_port = DPRODDataService(
            id=input_port_uri,
            label="User Prompt Service",
            endpoint_url=f"{self.base_uri}/api/agents/{agent_name}/chat",
            access_service_of=DPRODDistribution(
                format="application/json",
                is_distribution_of=DPRODDataset(
                    id=f"{agent_uri}/dataset/input",
                    label="User Prompts",
                    conforms_to=f"{self.base_uri}/schema/UserPrompt"
                )
            )
        )
        
        # Create output port (agent responses)
        output_port = DPRODDataService(
            id=output_port_uri,
            label="AI Response Service", 
            access_service_of=DPRODDistribution(
                format="application/json",
                is_distribution_of=DPRODDataset(
                    id=f"{agent_uri}/dataset/output",
                    label="AI Responses",
                    conforms_to=f"{self.base_uri}/schema/{agent_name}Response"
                )
            )
        )
        
        # Create observability port (metrics)
        observability_port = DPRODDataService(
            id=observability_port_uri,
            label="Observability Port",
            endpoint_url=f"{self.base_uri}/api/observability/{agent_name}",
            access_service_of=DPRODDistribution(
                format="application/json",
                is_distribution_of=DPRODDataset(
                    id=f"{agent_uri}/dataset/observability",
                    label="Agent Metrics",
                    conforms_to=f"{self.base_uri}/schema/AgentMetrics"
                )
            )
        )
        
        # Extract capabilities from agent config
        capabilities = self._extract_capabilities(agent_config)
        model_info = self._extract_model_info(agent_config)
        
        # Create DPROD data product
        data_product = DPRODDataProduct(
            id=agent_uri,
            label=agent_config.get("name", agent_name),
            description=agent_config.get("description", ""),
            input_ports=[input_port],
            output_ports=[output_port],
            observability_port=observability_port,
            capabilities=capabilities,
            model_info=model_info,
            performance_tier=self._assess_performance_tier(agent_config),
            privacy_level=self._determine_privacy_level(agent_config),
            conforms_to=f"{self.base_uri}/schema/AIAgent",
            created_at=datetime.now(),
            modified_at=datetime.now()
        )
        
        # Store in triple store
        self.triple_store.store_data_product(data_product)
        
        return data_product
    
    def _extract_capabilities(self, agent_config: Dict) -> List[str]:
        """Extract agent capabilities from configuration."""
        capabilities = []
        
        # Analyze agent name and description for capabilities
        name = agent_config.get("name", "").lower()
        description = agent_config.get("description", "").lower()
        
        capability_keywords = {
            "coding": ["code", "programming", "software", "development"],
            "reasoning": ["reasoning", "analysis", "logic", "problem-solving"],
            "multilingual": ["multilingual", "chinese", "french", "language"],
            "creative": ["creative", "writing", "content", "brainstorm"],
            "mathematical": ["math", "calculation", "equation", "proof"],
            "research": ["research", "search", "information", "current"],
            "local": ["local", "privacy", "offline", "ollama"],
            "fast": ["fast", "quick", "lightweight", "efficient"]
        }
        
        for capability, keywords in capability_keywords.items():
            if any(keyword in name or keyword in description for keyword in keywords):
                capabilities.append(capability)
        
        return capabilities
    
    def _extract_model_info(self, agent_config: Dict) -> Dict[str, Any]:
        """Extract model information from agent configuration."""
        model_info = {}
        
        # Try to get model from chat_model attribute
        if "chat_model" in agent_config:
            chat_model = agent_config["chat_model"]
            model_info["model_class"] = chat_model.__class__.__name__
            
            # Extract model name/ID
            if hasattr(chat_model, "model_name"):
                model_info["model_name"] = chat_model.model_name
            elif hasattr(chat_model, "model"):
                model_info["model_name"] = chat_model.model
                
            # Extract temperature
            if hasattr(chat_model, "temperature"):
                model_info["temperature"] = chat_model.temperature
                
        return model_info
    
    def _assess_performance_tier(self, agent_config: Dict) -> str:
        """Assess agent performance tier based on model characteristics."""
        model_name = self._extract_model_info(agent_config).get("model_name", "").lower()
        
        if any(model in model_name for model in ["gpt-4", "claude-3.5", "grok"]):
            return "high"
        elif any(model in model_name for model in ["gpt-3.5", "gemini", "mistral"]):
            return "medium"  
        else:
            return "standard"
    
    def _determine_privacy_level(self, agent_config: Dict) -> str:
        """Determine privacy level based on deployment type."""
        model_name = self._extract_model_info(agent_config).get("model_name", "").lower()
        
        if any(local_indicator in model_name for local_indicator in ["ollama", "qwen", "deepseek", "gemma"]):
            return "local"
        else:
            return "cloud"
```

### 3. Observability Framework

**Location**: `src/core/modules/dprod/observability/`

```python
# src/core/modules/dprod/observability/ObservabilityCollector.py
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import time

@dataclass
class AgentMetrics:
    """DPROD-compliant agent observability metrics."""
    
    agent_name: str
    timestamp: datetime
    conversation_id: Optional[str] = None
    
    # Performance metrics
    response_time_ms: float
    token_count_input: int
    token_count_output: int
    
    # Quality metrics
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    
    # Resource metrics
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    
    def to_dprod_observability(self) -> Dict[str, Any]:
        """Convert to DPROD observability format."""
        return {
            "@context": "https://ekgf.github.io/dprod/dprod.jsonld",
            "observabilityLog": {
                "agent": self.agent_name,
                "timestamp": self.timestamp.isoformat(),
                "conversationId": self.conversation_id,
                "metrics": {
                    "responseTimeMs": self.response_time_ms,
                    "tokenUsage": {
                        "input": self.token_count_input,
                        "output": self.token_count_output,
                        "total": self.token_count_input + self.token_count_output
                    },
                    "success": self.success,
                    "errorType": self.error_type,
                    "errorMessage": self.error_message,
                    "resourceUsage": {
                        "memoryMb": self.memory_usage_mb,
                        "cpuPercent": self.cpu_usage_percent
                    }
                },
                "conformsTo": "https://abi.naas.ai/schema/AgentObservability"
            }
        }

class ObservabilityCollector:
    """Collect observability metrics for AI agents."""
    
    def __init__(self, metrics_store: 'MetricsStore'):
        self.metrics_store = metrics_store
        self.active_requests: Dict[str, float] = {}  # Track request start times
    
    def start_request(self, agent_name: str, conversation_id: str) -> str:
        """Start tracking a request."""
        request_id = f"{agent_name}_{conversation_id}_{time.time()}"
        self.active_requests[request_id] = time.time()
        return request_id
    
    def end_request(self, request_id: str, agent_name: str, conversation_id: str, 
                   success: bool, token_input: int, token_output: int,
                   error_type: Optional[str] = None, error_message: Optional[str] = None) -> AgentMetrics:
        """End tracking and collect metrics."""
        
        start_time = self.active_requests.pop(request_id, time.time())
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        metrics = AgentMetrics(
            agent_name=agent_name,
            timestamp=datetime.now(),
            conversation_id=conversation_id,
            response_time_ms=response_time,
            token_count_input=token_input,
            token_count_output=token_output,
            success=success,
            error_type=error_type,
            error_message=error_message
        )
        
        # Store metrics
        self.metrics_store.store_metrics(metrics)
        
        return metrics
```

### 4. Enhanced AbiAgent Integration

**Location**: `src/core/modules/abi/agents/AbiAgent.py` (enhancement)

```python
# Enhancement to existing AbiAgent
class AbiAgent(IntentAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # DPROD components
        self.dprod_registry = AgentRegistryService(DPRODTripleStore())
        self.lineage_tracker = ConversationLineageTracker()
        self.observability_collector = ObservabilityCollector(MetricsStore())
        
        # Register all agents as DPROD data products on startup
        self._register_agents_as_data_products()
    
    def _register_agents_as_data_products(self):
        """Register all loaded agents as DPROD data products."""
        for agent in self.agents:
            agent_config = {
                "name": agent.name,
                "description": agent.description,
                "chat_model": agent._chat_model
            }
            self.dprod_registry.register_agent(agent.name, agent_config)
    
    def find_best_agent_by_capability(self, required_capabilities: List[str]) -> Optional[str]:
        """Use DPROD metadata to find agent with required capabilities."""
        
        # Build SPARQL query
        capabilities_filter = ' '.join([f'"{cap}"' for cap in required_capabilities])
        
        query = f"""
        PREFIX dprod: <https://ekgf.github.io/dprod/>
        PREFIX abi: <https://abi.naas.ai/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?agent ?label ?score
        WHERE {{
          ?agent a dprod:DataProduct .
          ?agent rdfs:label ?label .
          ?agent abi:capabilities ?cap .
          ?agent abi:performanceTier ?tier .
          
          FILTER(?cap IN ({capabilities_filter}))
          
          BIND(
            IF(?tier = "high", 3,
            IF(?tier = "medium", 2, 1)) AS ?score
          )
        }}
        ORDER BY DESC(?score)
        LIMIT 1
        """
        
        try:
            results = self.dprod_registry.triple_store.query(query)
            if results:
                # Extract agent name from URI
                agent_uri = results[0]['agent']
                agent_name = agent_uri.split('/')[-1]  # Get last part of URI
                return agent_name
        except Exception as e:
            logger.warning(f"DPROD query failed, falling back to default routing: {e}")
        
        return None
    
    def invoke_with_observability(self, input_data: str, conversation_id: str = None) -> Any:
        """Enhanced invoke with DPROD observability tracking."""
        
        # Start observability tracking
        request_id = self.observability_collector.start_request(
            agent_name="Abi",
            conversation_id=conversation_id or str(uuid.uuid4())
        )
        
        try:
            # Count input tokens (approximate)
            input_tokens = len(input_data.split())
            
            # Execute normal invoke
            result = super().invoke(input_data)
            
            # Count output tokens (approximate)
            output_tokens = len(str(result).split()) if result else 0
            
            # End observability tracking (success)
            metrics = self.observability_collector.end_request(
                request_id=request_id,
                agent_name="Abi", 
                conversation_id=conversation_id,
                success=True,
                token_input=input_tokens,
                token_output=output_tokens
            )
            
            return result
            
        except Exception as e:
            # End observability tracking (failure)
            metrics = self.observability_collector.end_request(
                request_id=request_id,
                agent_name="Abi",
                conversation_id=conversation_id,
                success=False,
                token_input=len(input_data.split()),
                token_output=0,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise
```

### 5. SPARQL Query Interface

**Location**: `src/core/modules/dprod/query/`

```python
# src/core/modules/dprod/query/SPARQLEndpoint.py
from fastapi import FastAPI, HTTPException
from typing import Dict, List, Any
from ..storage.DPRODTripleStore import DPRODTripleStore

class SPARQLEndpoint:
    """SPARQL query endpoint for DPROD data."""
    
    def __init__(self, triple_store: DPRODTripleStore):
        self.triple_store = triple_store
        self.app = FastAPI()
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes for SPARQL queries."""
        
        @self.app.post("/sparql")
        async def execute_sparql(query: str) -> Dict[str, Any]:
            """Execute SPARQL query against DPROD data."""
            try:
                results = self.triple_store.query(query)
                return {
                    "status": "success",
                    "results": results,
                    "count": len(results)
                }
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.get("/agents")
        async def list_agents() -> List[Dict[str, Any]]:
            """List all agents as DPROD data products."""
            query = """
            PREFIX dprod: <https://ekgf.github.io/dprod/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX abi: <https://abi.naas.ai/schema/>
            
            SELECT ?agent ?label ?description ?capabilities ?performanceTier ?privacyLevel
            WHERE {
              ?agent a dprod:DataProduct .
              ?agent rdfs:label ?label .
              ?agent rdfs:comment ?description .
              ?agent abi:capabilities ?capabilities .
              ?agent abi:performanceTier ?performanceTier .
              ?agent abi:privacyLevel ?privacyLevel .
            }
            """
            return self.triple_store.query(query)
        
        @self.app.get("/agents/by-capability/{capability}")
        async def find_agents_by_capability(capability: str) -> List[Dict[str, Any]]:
            """Find agents with specific capability."""
            query = f"""
            PREFIX dprod: <https://ekgf.github.io/dprod/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX abi: <https://abi.naas.ai/schema/>
            
            SELECT ?agent ?label ?performanceTier
            WHERE {{
              ?agent a dprod:DataProduct .
              ?agent rdfs:label ?label .
              ?agent abi:capabilities "{capability}" .
              ?agent abi:performanceTier ?performanceTier .
            }}
            ORDER BY DESC(?performanceTier)
            """
            return self.triple_store.query(query)
        
        @self.app.get("/lineage/{conversation_id}")
        async def get_conversation_lineage(conversation_id: str) -> List[Dict[str, Any]]:
            """Get conversation lineage for a specific conversation."""
            query = f"""
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX abi: <https://abi.naas.ai/schema/>
            
            SELECT ?step ?from_agent ?to_agent ?timestamp ?activity
            WHERE {{
              ?conversation abi:conversationId "{conversation_id}" .
              ?conversation prov:hadStep ?step .
              ?step prov:used ?from_agent .
              ?step prov:generated ?to_agent .
              ?step prov:atTime ?timestamp .
              ?step prov:wasAssociatedWith ?activity .
            }}
            ORDER BY ?timestamp
            """
            return self.triple_store.query(query)
```

## Data Flow Architecture

### Agent Registration Flow
```
Agent Startup → Extract Metadata → Create DPROD Model → Store in Triple Store → Expose via SPARQL
```

### Conversation Flow with Observability
```
User Input → Start Metrics → Route to Agent → Execute → Collect Metrics → Store Observability → Track Lineage
```

### Query Flow
```
SPARQL Query → Triple Store → Result Processing → JSON Response → Client Integration
```

## Performance Considerations

### RDF Storage Optimization
- **Indexing Strategy**: Index frequently queried properties (capabilities, performance tier)
- **Caching Layer**: Redis cache for common SPARQL queries
- **Query Optimization**: Pre-compiled queries for agent discovery

### Observability Overhead
- **Async Collection**: Non-blocking metrics collection
- **Batch Processing**: Batch metrics storage to reduce I/O
- **Sampling**: Sample high-frequency operations for large deployments

### Scalability Patterns
- **Horizontal Scaling**: Distribute triple store across nodes
- **Query Federation**: Federate queries across multiple stores
- **Caching Strategy**: Multi-level caching for metadata and metrics

---

This technical architecture provides the foundation for implementing DPROD compliance in ABI while maintaining performance and scalability requirements.
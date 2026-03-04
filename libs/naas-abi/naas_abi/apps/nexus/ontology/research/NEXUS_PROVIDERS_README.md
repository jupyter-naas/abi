# NEXUS Providers Ontology - Implementation Guide

**File:** `nexus_providers.ttl`  
**Standard:** ISO 21383-2 (Basic Formal Ontology)  
**Format:** RDF/Turtle  
**Version:** 1.0  
**Date:** 2026-02-09

---

## Overview

This ontology demonstrates the **concrete implementation** of BFO 7 Buckets alignment for NEXUS's AI provider integration system. It provides formal semantics for heterogeneous streaming protocols, capabilities, and provider characteristics.

### Purpose

1. **Formal Knowledge Representation** - Capture provider capabilities, protocols, and relationships in machine-readable format
2. **Automated Reasoning** - Enable SPARQL queries for capability discovery, compatibility validation, and adapter selection
3. **Interoperability** - Provide shared vocabulary for integrating diverse AI providers (OpenAI, Anthropic, ABI/Naas, Ollama)
4. **Standards Compliance** - Align with ISO 21383-2 (BFO) for scientific rigor

---

## Quick Start

### Load the Ontology

```python
from rdflib import Graph, Namespace

# Load ontology
g = Graph()
g.parse("/Users/jrvmac/nexus/docs/research/nexus_providers.ttl", format="turtle")

# Define namespaces
NEXUS = Namespace("http://ontology.naas.ai/nexus/")
BFO = Namespace("http://purl.obolibrary.org/obo/")
```

### Example Query 1: Find W3C SSE Providers

```python
query = """
PREFIX nexus: <http://ontology.naas.ai/nexus/>

SELECT ?provider ?label WHERE {
    ?provider nexus:implementsProtocol nexus:W3C_SSE .
    ?provider rdfs:label ?label .
}
"""

for row in g.query(query):
    print(f"Provider: {row.label}")
# Output: Provider: ABI Forvis Mazars
```

### Example Query 2: Find Providers with Function Calling

```python
query = """
PREFIX nexus: <http://ontology.naas.ai/nexus/>

SELECT ?provider ?label WHERE {
    ?provider nexus:hasCapability nexus:FunctionCallingCapability .
    ?provider rdfs:label ?label .
}
"""

for row in g.query(query):
    print(f"Provider: {row.label}")
# Output: 
# Provider: OpenAI
# Provider: Anthropic
```

### Example Query 3: Check Protocol Compliance

```python
query = """
PREFIX nexus: <http://ontology.naas.ai/nexus/>

ASK {
    nexus:OpenAI nexus:implementsProtocol nexus:W3C_SSE .
}
"""

result = g.query(query).askAnswer
print(f"OpenAI implements W3C SSE: {result}")
# Output: OpenAI implements W3C SSE: False
```

---

## BFO 7 Buckets Structure

The ontology maps NEXUS concepts to BFO's fundamental categories:

| BFO Bucket | BFO Class | NEXUS Classes | Example Instances |
|------------|-----------|---------------|-------------------|
| **1. Process** (WHAT) | `BFO_0000015` | `StreamEvent`, `ContentEvent`, `LinkEvent`, `ToolCallEvent` | `nexus:Event001`, `nexus:Event002` |
| **2. Temporal Region** (WHEN) | `BFO_0000008` | `StreamSequence`, `StreamLifecycle` | Event timestamps, ordering |
| **3. Material Entity** (WHO) | `BFO_0000040` | `AIProvider`, `AIModel`, `AIAgent` | `nexus:OpenAI`, `nexus:GPT4o` |
| **4. Site** (WHERE) | `BFO_0000029` | `APIEndpoint`, `Workspace` | `https://api.openai.com` |
| **5. Gen. Dep. Continuant** (HOW WE KNOW) | `BFO_0000031` | `StreamingProtocol`, `W3C_SSE`, `OpenAI_SSE` | Protocol specifications |
| **6. Quality** (HOW IT IS) | `BFO_0000019` | `EventProperty`, `Latency`, `TokenCount` | Performance metrics |
| **7. Role/Disposition** (WHY) | `BFO_0000023`/`BFO_0000016` | `ProviderRole`, `StreamingCapability` | `InferenceProvider`, `MultiLineDataCapability` |

---

## Class Hierarchy

### Bucket 1: Process Hierarchy (Events)

```
bfo:BFO_0000015 (process)
└── nexus:StreamEvent
    ├── nexus:ContentEvent
    ├── nexus:ThinkingEvent
    ├── nexus:ToolCallEvent
    ├── nexus:ToolResultEvent
    ├── nexus:LinkEvent
    ├── nexus:FileEvent
    ├── nexus:ErrorEvent
    └── nexus:DoneEvent
```

**Usage:** All streaming events are processes that occur over time with participants.

### Bucket 3: Material Entity Hierarchy (Providers)

```
bfo:BFO_0000040 (material entity)
├── nexus:AIProvider
│   ├── nexus:OpenAIProvider
│   ├── nexus:AnthropicProvider
│   ├── nexus:ABIProvider
│   └── nexus:OllamaProvider
├── nexus:AIModel
└── nexus:AIAgent
```

**Usage:** Providers, models, and agents are material entities that participate in streaming processes.

### Bucket 5: Protocol Hierarchy (Information)

```
bfo:BFO_0000031 (generically dependent continuant)
├── nexus:StreamingProtocol
│   ├── nexus:ServerSentEvents
│   │   ├── nexus:W3C_SSE
│   │   └── nexus:Anthropic_SSE
│   └── nexus:OpenAI_SSE
└── nexus:EventFormat
    ├── nexus:JSONFormat
    └── nexus:PlainTextFormat
```

**Usage:** Protocols are abstract patterns that exist independently of implementations.

### Bucket 7: Capability Hierarchy (Dispositions)

```
bfo:BFO_0000016 (disposition)
├── nexus:StreamingCapability
│   └── nexus:SSECapability
│       ├── nexus:MultiLineDataCapability
│       └── nexus:SingleLineDataCapability
├── nexus:FunctionCallingCapability
└── nexus:VisionCapability
```

**Usage:** Capabilities are intrinsic properties that providers possess based on their implementation.

---

## Concrete Instances

### Provider Instances

#### 1. OpenAI

```turtle
nexus:OpenAI a nexus:OpenAIProvider ;
    nexus:hasEndpoint "https://api.openai.com/v1/chat/completions" ;
    nexus:implementsProtocol nexus:OpenAI_SSE ;
    nexus:hasCapability nexus:SingleLineDataCapability ;
    nexus:hasCapability nexus:FunctionCallingCapability ;
    nexus:hasCapability nexus:VisionCapability ;
    nexus:hasRole nexus:InferenceProvider ;
    nexus:hasRole nexus:ToolProvider ;
    nexus:hasRole nexus:MultimodalProvider .
```

**Key Characteristics:**
- Custom JSON-per-line format (not true SSE)
- Single `data:` line per chunk
- No `event:` types
- Full multimodal support

#### 2. Anthropic

```turtle
nexus:Anthropic a nexus:AnthropicProvider ;
    nexus:hasEndpoint "https://api.anthropic.com/v1/messages" ;
    nexus:implementsProtocol nexus:Anthropic_SSE ;
    nexus:hasCapability nexus:SingleLineDataCapability ;
    nexus:hasCapability nexus:FunctionCallingCapability ;
    nexus:hasCapability nexus:VisionCapability .
```

**Key Characteristics:**
- W3C SSE with `event:` types
- Lifecycle events (start, delta, stop)
- Single `data:` per event (best practice)
- Structured JSON payloads

#### 3. ABI/Naas (Forvis Mazars)

```turtle
nexus:ABIForvisMazars a nexus:ABIProvider ;
    nexus:hasEndpoint "https://abi-forvismazars.default.space.naas.ai" ;
    nexus:implementsProtocol nexus:W3C_SSE ;
    nexus:hasCapability nexus:MultiLineDataCapability ;
    nexus:hasRole nexus:InferenceProvider .
```

**Key Characteristics:**
- **Strictly W3C SSE compliant**
- Multiple `data:` lines per event (e.g., links split across lines)
- Plain text format (not JSON)
- Unique in industry for true W3C compliance

#### 4. Ollama

```turtle
nexus:Ollama a nexus:OllamaProvider ;
    nexus:hasEndpoint "http://localhost:11434/api/chat" ;
    nexus:implementsProtocol nexus:OpenAI_SSE ;
    nexus:hasCapability nexus:SingleLineDataCapability .
```

**Key Characteristics:**
- Local inference
- OpenAI-compatible API
- No cloud dependency

---

## Critical Distinctions

### Multi-line vs. Single-line Data

**W3C SSE Standard (ABI):**
```
event: ai_message
data: First part of content
data: Second part (e.g., a link)
data: Third part

<blank line dispatches event>
```

**OpenAI/Anthropic Pattern:**
```
data: {"content": "Complete chunk"}

data: {"content": "Next chunk"}
```

**Ontology Representation:**
- `nexus:MultiLineDataCapability` → ABI
- `nexus:SingleLineDataCapability` → OpenAI, Anthropic

**Query to find multi-line providers:**
```sparql
SELECT ?provider WHERE {
    ?provider nexus:hasCapability nexus:MultiLineDataCapability .
}
```

---

## Use Cases

### Use Case 1: Adapter Selection

**Problem:** Given a provider, which adapter should NEXUS use?

**Solution:**
```python
def get_adapter_for_provider(provider_id: str) -> str:
    query = f"""
    PREFIX nexus: <http://ontology.naas.ai/nexus/>
    
    SELECT ?protocol WHERE {{
        nexus:{provider_id} nexus:implementsProtocol ?protocol .
    }}
    """
    
    result = g.query(query)
    protocol = list(result)[0][0]
    
    # Map protocol to adapter
    adapter_map = {
        NEXUS.W3C_SSE: "ABIAdapter",
        NEXUS.OpenAI_SSE: "OpenAIAdapter",
        NEXUS.Anthropic_SSE: "AnthropicAdapter"
    }
    
    return adapter_map[protocol]

# Example
adapter = get_adapter_for_provider("ABIForvisMazars")
print(adapter)  # Output: ABIAdapter
```

### Use Case 2: Capability Validation

**Problem:** Does this provider support function calling?

**Solution:**
```python
def provider_supports_function_calling(provider_id: str) -> bool:
    query = f"""
    PREFIX nexus: <http://ontology.naas.ai/nexus/>
    
    ASK {{
        nexus:{provider_id} nexus:hasCapability nexus:FunctionCallingCapability .
    }}
    """
    
    return g.query(query).askAnswer

# Example
print(provider_supports_function_calling("OpenAI"))  # True
print(provider_supports_function_calling("ABIForvisMazars"))  # False
```

### Use Case 3: Provider Discovery by Capability

**Problem:** Find all providers that support multimodal input.

**Solution:**
```sparql
PREFIX nexus: <http://ontology.naas.ai/nexus/>

SELECT ?provider ?label WHERE {
    ?provider nexus:hasCapability nexus:VisionCapability .
    ?provider rdfs:label ?label .
}
```

**Result:**
- OpenAI
- Anthropic

### Use Case 4: Protocol Validation

**Problem:** Verify that a new provider claims the correct protocol.

**Solution:**
```python
def validate_provider_protocol_claim(provider_id: str, claimed_protocol: str) -> bool:
    query = f"""
    PREFIX nexus: <http://ontology.naas.ai/nexus/>
    
    ASK {{
        nexus:{provider_id} nexus:implementsProtocol nexus:{claimed_protocol} .
    }}
    """
    
    actual = g.query(query).askAnswer
    
    if not actual:
        print(f"WARNING: {provider_id} does not implement {claimed_protocol}")
        print("Check provider configuration!")
    
    return actual
```

### Use Case 5: Find Models by Provider

**Problem:** List all models available from ABI.

**Solution:**
```sparql
PREFIX nexus: <http://ontology.naas.ai/nexus/>

SELECT ?model ?label WHERE {
    ?model nexus:providedBy nexus:ABIForvisMazars .
    ?model rdfs:label ?label .
}
```

**Result:**
- ForvisMazars Corporate Agent
- BOB - Orchestrator

---

## Integration with NEXUS Code

### 1. Ontology-Driven Registry

```python
# apps/api/app/services/providers/ontology_registry.py

from rdflib import Graph, Namespace, URIRef
from typing import Type, Optional

NEXUS = Namespace("http://ontology.naas.ai/nexus/")
BFO = Namespace("http://purl.obolibrary.org/obo/")

class OntologyRegistry:
    def __init__(self, ontology_path: str):
        self.graph = Graph()
        self.graph.parse(ontology_path, format="turtle")
    
    def get_protocol_for_provider(self, provider_id: str) -> Optional[str]:
        """Query ontology for provider's protocol"""
        query = f"""
        PREFIX nexus: <http://ontology.naas.ai/nexus/>
        
        SELECT ?protocol WHERE {{
            nexus:{provider_id} nexus:implementsProtocol ?protocol .
        }}
        """
        
        results = list(self.graph.query(query))
        if results:
            protocol_uri = results[0][0]
            return protocol_uri.split('#')[-1].split('/')[-1]
        return None
    
    def get_capabilities(self, provider_id: str) -> list[str]:
        """Get all capabilities for provider"""
        query = f"""
        PREFIX nexus: <http://ontology.naas.ai/nexus/>
        
        SELECT ?capability WHERE {{
            nexus:{provider_id} nexus:hasCapability ?capability .
        }}
        """
        
        results = self.graph.query(query)
        return [str(row[0]).split('/')[-1] for row in results]
    
    def find_providers_with_capability(self, capability: str) -> list[str]:
        """Find all providers with given capability"""
        query = f"""
        PREFIX nexus: <http://ontology.naas.ai/nexus/>
        
        SELECT ?provider ?label WHERE {{
            ?provider nexus:hasCapability nexus:{capability} .
            ?provider rdfs:label ?label .
        }}
        """
        
        results = self.graph.query(query)
        return [str(row.label) for row in results]

# Usage
registry = OntologyRegistry("/Users/jrvmac/nexus/docs/research/nexus_providers.ttl")

protocol = registry.get_protocol_for_provider("ABIForvisMazars")
print(f"Protocol: {protocol}")  # W3C_SSE

capabilities = registry.get_capabilities("OpenAI")
print(f"Capabilities: {capabilities}")
# ['SingleLineDataCapability', 'FunctionCallingCapability', 'VisionCapability']

providers = registry.find_providers_with_capability("FunctionCallingCapability")
print(f"Providers with function calling: {providers}")
# ['OpenAI', 'Anthropic']
```

### 2. Event Validation

```python
# apps/api/app/services/providers/event_validator.py

from rdflib import Graph, Namespace

class BFOEventValidator:
    """Validate StreamEvents against BFO constraints"""
    
    def __init__(self, ontology: Graph):
        self.ontology = ontology
        self.NEXUS = Namespace("http://ontology.naas.ai/nexus/")
        self.BFO = Namespace("http://purl.obolibrary.org/obo/")
    
    def validate_event(self, event: StreamEvent) -> bool:
        """Ensure event satisfies BFO process constraints"""
        
        # BFO Constraint 1: Process must have participant (BFO_0000057)
        if not event.agent_id:
            raise ValidationError("StreamEvent must have participant (BFO requirement)")
        
        # BFO Constraint 2: Process must occupy temporal region (BFO_0000199)
        if not event.timestamp:
            raise ValidationError("StreamEvent must have timestamp")
        
        # NEXUS Constraint: Event must be valid subclass
        if not self._is_valid_event_type(event.type):
            raise ValidationError(f"Unknown event type: {event.type}")
        
        return True
    
    def _is_valid_event_type(self, event_type: str) -> bool:
        """Check if event_type is defined in ontology"""
        event_class = self.NEXUS[f"{event_type}Event"]
        
        query = f"""
        ASK {{
            <{event_class}> rdfs:subClassOf* <{self.NEXUS.StreamEvent}> .
        }}
        """
        
        return self.ontology.query(query).askAnswer

# Usage
validator = BFOEventValidator(registry.graph)

event = StreamEvent(
    type=StreamEventType.CONTENT,
    content="Hello",
    timestamp=datetime.utcnow(),
    agent_id="agent-123"
)

validator.validate_event(event)  # Passes
```

---

## Advanced Queries

### Query 1: Find Incompatible Providers

```sparql
# Providers that claim W3C SSE but don't have multi-line capability
PREFIX nexus: <http://ontology.naas.ai/nexus/>

SELECT ?provider ?label WHERE {
    ?provider nexus:implementsProtocol nexus:W3C_SSE .
    ?provider rdfs:label ?label .
    FILTER NOT EXISTS {
        ?provider nexus:hasCapability nexus:MultiLineDataCapability .
    }
}
```

**Expected Result:** None (if ontology is correct)

### Query 2: Provider Comparison Matrix

```sparql
PREFIX nexus: <http://ontology.naas.ai/nexus/>

SELECT ?provider 
       (COUNT(?capability) AS ?capabilityCount)
       (GROUP_CONCAT(?role; separator=", ") AS ?roles)
WHERE {
    ?provider a nexus:AIProvider .
    ?provider nexus:hasCapability ?capability .
    ?provider nexus:hasRole ?role .
}
GROUP BY ?provider
ORDER BY DESC(?capabilityCount)
```

### Query 3: Validate Event Participant Chain

```sparql
# Check that event → agent → model → provider chain is valid
PREFIX nexus: <http://ontology.naas.ai/nexus/>
PREFIX bfo: <http://purl.obolibrary.org/obo/>

SELECT ?event ?agent ?model ?provider WHERE {
    ?event bfo:BFO_0000057 ?agent .  # event has participant agent
    ?agent nexus:hasModel ?model .
    ?model nexus:providedBy ?provider .
}
```

---

## Maintenance & Evolution

### Adding New Providers

To add a new provider:

1. **Define provider class** (if needed):
```turtle
nexus:NewProvider a owl:Class ;
    rdfs:subClassOf nexus:AIProvider ;
    rdfs:label "New Provider"@en .
```

2. **Create instance**:
```turtle
nexus:MyNewProvider a nexus:NewProvider ;
    rdfs:label "My New AI Service"@en ;
    nexus:hasEndpoint "https://api.example.com"^^xsd:anyURI ;
    nexus:implementsProtocol nexus:W3C_SSE ;  # or custom
    nexus:hasCapability nexus:SingleLineDataCapability ;
    nexus:hasRole nexus:InferenceProvider .
```

3. **Validate**:
```python
# Check that provider is correctly classified
query = """
ASK {
    nexus:MyNewProvider a nexus:AIProvider .
}
"""
assert g.query(query).askAnswer == True
```

### Adding New Capabilities

```turtle
nexus:AudioCapability a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000016 ;  # disposition
    rdfs:label "Audio Capability"@en ;
    skos:definition "Can process audio input"@en .

# Add to provider
nexus:OpenAI nexus:hasCapability nexus:AudioCapability .
```

### Versioning

Track ontology versions in metadata:

```turtle
nexus:ProvidersOntology owl:versionInfo "1.1" ;
    dc:date "2026-03-01"^^xsd:date ;
    rdfs:comment "Added audio capabilities"@en .
```

---

## Testing

### Unit Tests

```python
# tests/test_ontology.py

import pytest
from rdflib import Graph, Namespace

@pytest.fixture
def ontology():
    g = Graph()
    g.parse("docs/research/nexus_providers.ttl", format="turtle")
    return g

def test_abi_implements_w3c_sse(ontology):
    """ABI must implement W3C SSE"""
    NEXUS = Namespace("http://ontology.naas.ai/nexus/")
    
    query = """
    PREFIX nexus: <http://ontology.naas.ai/nexus/>
    ASK {
        nexus:ABIForvisMazars nexus:implementsProtocol nexus:W3C_SSE .
    }
    """
    
    assert ontology.query(query).askAnswer == True

def test_openai_has_vision(ontology):
    """OpenAI must have vision capability"""
    query = """
    PREFIX nexus: <http://ontology.naas.ai/nexus/>
    ASK {
        nexus:OpenAI nexus:hasCapability nexus:VisionCapability .
    }
    """
    
    assert ontology.query(query).askAnswer == True

def test_abi_no_function_calling(ontology):
    """ABI should not have function calling"""
    query = """
    PREFIX nexus: <http://ontology.naas.ai/nexus/>
    ASK {
        nexus:ABIForvisMazars nexus:hasCapability nexus:FunctionCallingCapability .
    }
    """
    
    assert ontology.query(query).askAnswer == False
```

### Integration Tests

```python
def test_adapter_selection_from_ontology():
    """Test that adapter selection uses ontology correctly"""
    registry = OntologyRegistry("docs/research/nexus_providers.ttl")
    
    # ABI → ABIAdapter
    protocol = registry.get_protocol_for_provider("ABIForvisMazars")
    assert protocol == "W3C_SSE"
    
    # OpenAI → OpenAIAdapter
    protocol = registry.get_protocol_for_provider("OpenAI")
    assert protocol == "OpenAI_SSE"
```

---

## Visualization

### Generate Class Diagram

```python
from rdflib import Graph
from rdflib.tools.rdf2dot import rdf2dot
import pydot

g = Graph()
g.parse("ontology/nexus_providers.ttl", format="turtle")

# Generate DOT format
dot_data = rdf2dot(g, stream=True)

# Render to PNG
(graph,) = pydot.graph_from_dot_data(dot_data)
graph.write_png("docs/ontology_diagram.png")
```

---

## Resources

### Documentation
- BFO Specification: https://github.com/BFO-ontology/BFO-2020
- ISO 21383-2:2024: https://www.iso.org/standard/79452.html
- W3C SSE Spec: https://html.spec.whatwg.org/multipage/server-sent-events.html
- RDFLib Documentation: https://rdflib.readthedocs.io/

### Related NEXUS Docs
- `ONTOLOGY_PROVIDER_ALIGNMENT.md` - Full specification
- `SSE_STREAMING_STANDARDS.md` - Protocol comparison
- `ABI_INTEGRATION_GAPS.md` - ABI-specific analysis
- `PROVIDER_ADAPTER_ARCHITECTURE.md` - Technical implementation

### Tools
- **Protégé** - Ontology editor: https://protege.stanford.edu/
- **SPARQL Playground** - Query testing: https://yasgui.triply.cc/
- **RDFLib** - Python RDF library: `pip install rdflib`

---

## FAQ

**Q: Why use an ontology instead of just code?**  
A: Ontologies enable:
- **Reasoning** - Infer new facts from existing knowledge
- **Validation** - Ensure consistency via formal constraints
- **Interoperability** - Shared vocabulary across systems
- **Documentation** - Self-documenting knowledge base

**Q: Can I query this from the frontend?**  
A: Yes! Use SPARQL.js or query via API:
```javascript
fetch('/api/ontology/query', {
  method: 'POST',
  body: JSON.stringify({ query: 'SELECT ?provider WHERE {...}' })
})
```

**Q: How do I update the ontology?**  
A: Edit `nexus_providers.ttl`, validate with Protégé, commit. Ontology is loaded at runtime.

**Q: Does this impact performance?**  
A: No. Ontology queries happen at:
- **Startup** - Load provider metadata
- **Configuration** - Select adapter for new provider
- **Validation** - Check event constraints (dev mode only)

Runtime streaming uses cached adapter instances, not ontology queries.

---

*Last Updated: 2026-02-10*  
*Ontology File: `docs/research/nexus_providers.ttl`*  
*Standard: ISO 21383-2 (BFO)*

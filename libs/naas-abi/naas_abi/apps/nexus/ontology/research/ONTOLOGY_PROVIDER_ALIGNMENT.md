# NEXUS Provider Ontology - BFO 7 Buckets Alignment

**Standard:** ISO 21383-2 (Basic Formal Ontology)  
**Version:** 2.0  
**Date:** 2026-02-09  
**Status:** Specification Draft

---

## Executive Summary

NEXUS must operate as a **protocol-agnostic AI orchestration hub** that integrates heterogeneous AI providers (OpenAI, Anthropic, ABI/Naas, etc.) with fundamentally different streaming protocols, data formats, and architectural patterns.

**Problem:** Current implementations force all providers into OpenAI's pseudo-SSE format, breaking W3C-compliant systems and limiting extensibility.

**Solution:** Define a formal ontology using BFO 7 Buckets that:
1. Normalizes heterogeneous streaming protocols into unified semantics
2. Preserves provider-specific capabilities without forcing lowest-common-denominator
3. Enables reasoning about provider compatibility, capabilities, and interoperability
4. Provides a foundation for automated adapter generation and validation

---

## 1. BFO 7 Buckets Overview

The Basic Formal Ontology (BFO) provides a top-level ontology for scientific and information systems. The "7 Buckets" represent fundamental categories:

| Bucket | BFO Class | Question | Domain Example |
|--------|-----------|----------|----------------|
| 1 | Process | **WHAT** | A streaming response event |
| 2 | Temporal Region | **WHEN** | Event timestamp, sequence order |
| 3 | Material Entity | **WHO** | AI model, agent, user |
| 4 | Site | **WHERE** | API endpoint, workspace, infrastructure |
| 5 | Generically Dependent Continuant | **HOW WE KNOW** | Protocol specification, API format |
| 6 | Quality | **HOW IT IS** | Event properties, metadata |
| 7 | Role/Disposition | **WHY** | Provider capability, agent purpose |

---

## 2. Mapping NEXUS Streaming Architecture to BFO

### 2.1 Process (WHAT happens)

**BFO Definition:** An occurrent that has temporal parts and material participants.

**NEXUS Mapping:** `StreamEvent` - The fundamental unit of streaming interaction

```turtle
@prefix nexus: <http://ontology.naas.ai/nexus/> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .

nexus:StreamEvent a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000015 ;  # process
    rdfs:label "Stream Event"@en ;
    skos:definition "A discrete event in an AI streaming response, representing content generation, tool invocation, or metadata transmission"@en .

# Event Type Hierarchy
nexus:ContentEvent a owl:Class ;
    rdfs:subClassOf nexus:StreamEvent ;
    rdfs:label "Content Generation Event"@en ;
    skos:example "Text chunk produced by LLM"@en .

nexus:ThinkingEvent a owl:Class ;
    rdfs:subClassOf nexus:StreamEvent ;
    rdfs:label "Reasoning Event"@en ;
    skos:example "Chain-of-thought reasoning visible to user"@en .

nexus:ToolCallEvent a owl:Class ;
    rdfs:subClassOf nexus:StreamEvent ;
    rdfs:label "Tool Invocation Event"@en ;
    skos:example "Function call to external API"@en .

nexus:ToolResultEvent a owl:Class ;
    rdfs:subClassOf nexus:StreamEvent ;
    rdfs:label "Tool Result Event"@en ;
    skos:example "Return value from function execution"@en .

nexus:FileEvent a owl:Class ;
    rdfs:subClassOf nexus:StreamEvent ;
    rdfs:label "File Reference Event"@en ;
    skos:example "Attachment, download link, PowerPoint presentation"@en .

nexus:LinkEvent a owl:Class ;
    rdfs:subClassOf nexus:StreamEvent ;
    rdfs:label "Hyperlink Event"@en ;
    skos:example "URL reference in response"@en .

nexus:ErrorEvent a owl:Class ;
    rdfs:subClassOf nexus:StreamEvent ;
    rdfs:label "Error Condition Event"@en ;
    skos:example "API failure, timeout, invalid input"@en .

nexus:MetadataEvent a owl:Class ;
    rdfs:subClassOf nexus:StreamEvent ;
    rdfs:label "Metadata Event"@en ;
    skos:example "Token usage, model version, processing time"@en .

nexus:DoneEvent a owl:Class ;
    rdfs:subClassOf nexus:StreamEvent ;
    rdfs:label "Stream Completion Event"@en ;
    skos:example "Final event signaling end of response"@en .
```

**Implementation:**
```python
class StreamEventType(Enum):
    CONTENT = "content"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE = "file"
    LINK = "link"
    ERROR = "error"
    METADATA = "metadata"
    DONE = "done"
```

---

### 2.2 Temporal Region (WHEN it happens)

**BFO Definition:** An occurrent over which processes unfold; represents time.

**NEXUS Mapping:** Event sequencing, timestamps, stream lifecycle

```turtle
nexus:StreamSequence a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000008 ;  # temporal region
    rdfs:label "Stream Event Sequence"@en ;
    skos:definition "The temporal ordering of events within a streaming response"@en .

nexus:hasEventIndex a owl:DatatypeProperty ;
    rdfs:domain nexus:StreamEvent ;
    rdfs:range xsd:integer ;
    rdfs:label "has event index"@en ;
    skos:definition "Position of event in stream sequence"@en .

nexus:hasTimestamp a owl:DatatypeProperty ;
    rdfs:domain nexus:StreamEvent ;
    rdfs:range xsd:dateTime ;
    rdfs:label "has timestamp"@en ;
    skos:definition "UTC timestamp when event was generated"@en .

nexus:precedes a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000063 ;  # precedes
    rdfs:domain nexus:StreamEvent ;
    rdfs:range nexus:StreamEvent ;
    rdfs:label "precedes"@en .

# Stream Lifecycle States
nexus:StreamLifecycle a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000008 ;
    rdfs:label "Stream Lifecycle"@en .

nexus:InitiatingPhase a owl:Class ;
    rdfs:subClassOf nexus:StreamLifecycle ;
    rdfs:label "Initiating Phase"@en ;
    skos:example "Connection established, first event not yet received"@en .

nexus:StreamingPhase a owl:Class ;
    rdfs:subClassOf nexus:StreamLifecycle ;
    rdfs:label "Streaming Phase"@en ;
    skos:example "Active streaming of events"@en .

nexus:CompletionPhase a owl:Class ;
    rdfs:subClassOf nexus:StreamLifecycle ;
    rdfs:label "Completion Phase"@en ;
    skos:example "DoneEvent received, stream closed"@en .

nexus:ErrorPhase a owl:Class ;
    rdfs:subClassOf nexus:StreamLifecycle ;
    rdfs:label "Error Phase"@en ;
    skos:example "Stream terminated due to error"@en .
```

**Properties:**
- Order matters: Event N must process before Event N+1
- Timestamps enable debugging and latency analysis
- Lifecycle phases map to connection states

---

### 2.3 Material Entity (WHO performs/receives)

**BFO Definition:** An independent continuant that has matter as part.

**NEXUS Mapping:** Providers, Models, Agents, Users

```turtle
nexus:AIProvider a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000040 ;  # material entity
    rdfs:label "AI Provider"@en ;
    skos:definition "An organization or service that provides AI model inference capabilities"@en ;
    skos:example "OpenAI, Anthropic, ABI/Naas, Ollama"@en .

nexus:OpenAIProvider a owl:Class ;
    rdfs:subClassOf nexus:AIProvider ;
    rdfs:label "OpenAI Provider"@en .

nexus:AnthropicProvider a owl:Class ;
    rdfs:subClassOf nexus:AIProvider ;
    rdfs:label "Anthropic Provider"@en .

nexus:ABIProvider a owl:Class ;
    rdfs:subClassOf nexus:AIProvider ;
    rdfs:label "ABI/Naas Provider"@en ;
    skos:definition "AI Builder Infrastructure provider using W3C-compliant SSE"@en .

nexus:OllamaProvider a owl:Class ;
    rdfs:subClassOf nexus:AIProvider ;
    rdfs:label "Ollama Provider"@en .

nexus:AIModel a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000040 ;
    rdfs:label "AI Model"@en ;
    skos:definition "A trained neural network capable of generating responses"@en ;
    skos:example "GPT-4o, Claude Opus, ForvisMazars_Corporate"@en .

nexus:AIAgent a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000040 ;
    rdfs:label "AI Agent"@en ;
    skos:definition "A configured instance of an AI model with specific role and capabilities"@en .

nexus:User a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000040 ;
    rdfs:label "User"@en ;
    skos:definition "A human participant in streaming conversation"@en .

# Relationships
nexus:providedBy a owl:ObjectProperty ;
    rdfs:domain nexus:AIModel ;
    rdfs:range nexus:AIProvider ;
    rdfs:label "provided by"@en .

nexus:hasModel a owl:ObjectProperty ;
    rdfs:domain nexus:AIAgent ;
    rdfs:range nexus:AIModel ;
    rdfs:label "has model"@en .

nexus:hasParticipant a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000057 ;  # has participant
    rdfs:domain nexus:StreamEvent ;
    rdfs:range [ owl:unionOf (nexus:AIAgent nexus:User) ] ;
    rdfs:label "has participant"@en .
```

---

### 2.4 Site (WHERE it occurs)

**BFO Definition:** A three-dimensional immaterial entity with boundaries.

**NEXUS Mapping:** API endpoints, workspaces, infrastructure locations

```turtle
nexus:APIEndpoint a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000029 ;  # site
    rdfs:label "API Endpoint"@en ;
    skos:definition "A network-accessible location where AI inference occurs"@en .

nexus:Workspace a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000029 ;
    rdfs:label "Workspace"@en ;
    skos:definition "A logical boundary containing users, agents, and conversations"@en .

nexus:InfrastructureRegion a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000029 ;
    rdfs:label "Infrastructure Region"@en ;
    skos:example "us-east-1, eu-west-1"@en .

nexus:occursAt a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000066 ;  # occurs in
    rdfs:domain nexus:StreamEvent ;
    rdfs:range nexus:APIEndpoint ;
    rdfs:label "occurs at"@en .

nexus:withinWorkspace a owl:ObjectProperty ;
    rdfs:domain nexus:StreamEvent ;
    rdfs:range nexus:Workspace ;
    rdfs:label "within workspace"@en .
```

---

### 2.5 Generically Dependent Continuant (HOW WE KNOW - Information)

**BFO Definition:** A pattern or content that exists in virtue of copies/instances.

**NEXUS Mapping:** Protocol specifications, streaming formats, API contracts

```turtle
nexus:StreamingProtocol a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000031 ;  # generically dependent continuant
    rdfs:label "Streaming Protocol"@en ;
    skos:definition "An abstract specification for how events are transmitted"@en .

# Protocol Hierarchy
nexus:ServerSentEvents a owl:Class ;
    rdfs:subClassOf nexus:StreamingProtocol ;
    rdfs:label "Server-Sent Events (SSE)"@en ;
    skos:definition "W3C standard for server-to-client event streaming"@en .

nexus:W3C_SSE a owl:Class ;
    rdfs:subClassOf nexus:ServerSentEvents ;
    rdfs:label "W3C SSE (Strict)"@en ;
    skos:definition "Strict W3C SSE with multiple data: lines per event"@en ;
    skos:example "ABI/Naas implementation"@en .

nexus:OpenAI_SSE a owl:Class ;
    rdfs:subClassOf nexus:StreamingProtocol ;
    rdfs:label "OpenAI Pseudo-SSE"@en ;
    skos:definition "Custom JSON-per-line format inspired by SSE"@en ;
    skos:note "Not W3C compliant - no event: types, single data: per chunk"@en .

nexus:Anthropic_SSE a owl:Class ;
    rdfs:subClassOf nexus:ServerSentEvents ;
    rdfs:label "Anthropic SSE"@en ;
    skos:definition "W3C SSE with event: types and lifecycle events"@en ;
    skos:note "Best practices: uses event types, single data: per event"@en .

# Format Specifications
nexus:EventFormat a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000031 ;
    rdfs:label "Event Format"@en .

nexus:JSONFormat a owl:Class ;
    rdfs:subClassOf nexus:EventFormat ;
    rdfs:label "JSON Format"@en .

nexus:PlainTextFormat a owl:Class ;
    rdfs:subClassOf nexus:EventFormat ;
    rdfs:label "Plain Text Format"@en .

nexus:MultilineTextFormat a owl:Class ;
    rdfs:subClassOf nexus:EventFormat ;
    rdfs:label "Multiline Text Format"@en ;
    skos:definition "Text split across multiple data: lines (W3C SSE)"@en .

# API Specifications
nexus:APISpecification a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000031 ;
    rdfs:label "API Specification"@en .

nexus:OpenAPISpec a owl:Class ;
    rdfs:subClassOf nexus:APISpecification ;
    rdfs:label "OpenAPI Specification"@en .

# Relationships
nexus:implementsProtocol a owl:ObjectProperty ;
    rdfs:domain nexus:AIProvider ;
    rdfs:range nexus:StreamingProtocol ;
    rdfs:label "implements protocol"@en .

nexus:usesFormat a owl:ObjectProperty ;
    rdfs:domain nexus:StreamEvent ;
    rdfs:range nexus:EventFormat ;
    rdfs:label "uses format"@en .

nexus:conformsTo a owl:ObjectProperty ;
    rdfs:domain nexus:StreamingProtocol ;
    rdfs:range nexus:APISpecification ;
    rdfs:label "conforms to"@en .
```

**Critical Insight:**

Different providers implement different protocols:
- **ABI/Naas** → W3C SSE (strict, multi-line data:)
- **OpenAI** → Pseudo-SSE (custom JSON, no event:)
- **Anthropic** → W3C SSE + best practices (event: types)

The protocol IS the "information pattern" that multiple implementations share.

---

### 2.6 Quality (HOW IT IS - Properties)

**BFO Definition:** A specifically dependent continuant that doesn't require realization.

**NEXUS Mapping:** Event properties, metadata, characteristics

```turtle
nexus:EventProperty a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000019 ;  # quality
    rdfs:label "Event Property"@en .

# Content Properties
nexus:ContentLength a owl:Class ;
    rdfs:subClassOf nexus:EventProperty ;
    rdfs:label "Content Length"@en .

nexus:TokenCount a owl:Class ;
    rdfs:subClassOf nexus:EventProperty ;
    rdfs:label "Token Count"@en .

nexus:Encoding a owl:Class ;
    rdfs:subClassOf nexus:EventProperty ;
    rdfs:label "Text Encoding"@en ;
    skos:example "UTF-8, UTF-16"@en .

# Stream Properties
nexus:Latency a owl:Class ;
    rdfs:subClassOf nexus:EventProperty ;
    rdfs:label "Event Latency"@en .

nexus:Throughput a owl:Class ;
    rdfs:subClassOf nexus:EventProperty ;
    rdfs:label "Stream Throughput"@en .

# Quality Measures
nexus:Reliability a owl:Class ;
    rdfs:subClassOf nexus:EventProperty ;
    rdfs:label "Stream Reliability"@en ;
    skos:definition "Probability of successful stream completion"@en .

nexus:Fidelity a owl:Class ;
    rdfs:subClassOf nexus:EventProperty ;
    rdfs:label "Event Fidelity"@en ;
    skos:definition "Accuracy of event representation vs. source"@en .

# Data Properties
nexus:hasContentLength a owl:DatatypeProperty ;
    rdfs:domain nexus:ContentEvent ;
    rdfs:range xsd:integer ;
    rdfs:label "has content length"@en .

nexus:hasTokenCount a owl:DatatypeProperty ;
    rdfs:domain nexus:StreamEvent ;
    rdfs:range xsd:integer ;
    rdfs:label "has token count"@en .

nexus:hasLatencyMs a owl:DatatypeProperty ;
    rdfs:domain nexus:StreamEvent ;
    rdfs:range xsd:float ;
    rdfs:label "has latency (milliseconds)"@en .
```

**Qualities are intrinsic to events** - they exist because the event exists.

---

### 2.7 Role & Disposition (WHY - Purpose & Capability)

**BFO Definition:** 
- **Role:** Externally-grounded realizable (social/institutional context)
- **Disposition:** Internally-grounded realizable (physical makeup)

**NEXUS Mapping:** Provider capabilities, adapter responsibilities, agent purposes

```turtle
# Roles (Externally-grounded)
nexus:ProviderRole a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000023 ;  # role
    rdfs:label "Provider Role"@en .

nexus:InferenceProvider a owl:Class ;
    rdfs:subClassOf nexus:ProviderRole ;
    rdfs:label "Inference Provider Role"@en ;
    skos:definition "Provides LLM inference capabilities"@en .

nexus:ToolProvider a owl:Class ;
    rdfs:subClassOf nexus:ProviderRole ;
    rdfs:label "Tool Provider Role"@en ;
    skos:definition "Provides function calling / tool use"@en .

nexus:MultimodalProvider a owl:Class ;
    rdfs:subClassOf nexus:ProviderRole ;
    rdfs:label "Multimodal Provider Role"@en ;
    skos:definition "Supports images, audio, video in addition to text"@en .

nexus:AdapterRole a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000023 ;
    rdfs:label "Adapter Role"@en ;
    skos:definition "Translates between provider format and NEXUS canonical format"@en .

nexus:AgentRole a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000023 ;
    rdfs:label "Agent Role"@en .

nexus:AssistantRole a owl:Class ;
    rdfs:subClassOf nexus:AgentRole ;
    rdfs:label "Assistant Role"@en .

nexus:OrchestratorRole a owl:Class ;
    rdfs:subClassOf nexus:AgentRole ;
    rdfs:label "Orchestrator Role"@en ;
    skos:example "BOB - Forvis Mazars orchestrator"@en .

nexus:SpecialistRole a owl:Class ;
    rdfs:subClassOf nexus:AgentRole ;
    rdfs:label "Specialist Role"@en ;
    skos:example "Market Intelligence, Corporate Data"@en .

# Dispositions (Internally-grounded)
nexus:StreamingCapability a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000016 ;  # disposition
    rdfs:label "Streaming Capability"@en .

nexus:SSECapability a owl:Class ;
    rdfs:subClassOf nexus:StreamingCapability ;
    rdfs:label "SSE Streaming Capability"@en .

nexus:MultiLineDataCapability a owl:Class ;
    rdfs:subClassOf nexus:SSECapability ;
    rdfs:label "Multi-line data: Capability"@en ;
    skos:definition "Ability to send multiple data: lines per event (W3C SSE)"@en .

nexus:FunctionCallingCapability a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000016 ;
    rdfs:label "Function Calling Capability"@en .

nexus:VisionCapability a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000016 ;
    rdfs:label "Vision Capability"@en .

# Capability Properties
nexus:hasCapability a owl:ObjectProperty ;
    rdfs:domain [ owl:unionOf (nexus:AIProvider nexus:AIModel nexus:AIAgent) ] ;
    rdfs:range [ owl:unionOf (nexus:StreamingCapability nexus:FunctionCallingCapability) ] ;
    rdfs:label "has capability"@en .

nexus:hasRole a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000196 ;  # bearer of
    rdfs:domain [ owl:unionOf (nexus:AIProvider nexus:AIAgent) ] ;
    rdfs:range [ owl:unionOf (nexus:ProviderRole nexus:AgentRole) ] ;
    rdfs:label "has role"@en .

nexus:realizes a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000055 ;  # realizes
    rdfs:domain nexus:StreamEvent ;
    rdfs:range [ owl:unionOf (nexus:ProviderRole nexus:AgentRole) ] ;
    rdfs:label "realizes"@en ;
    skos:definition "A streaming event realizes a role (e.g., assistant role realized by generating helpful response)"@en .
```

**Key Distinctions:**

- **Role** = Why provider/agent exists in social/business context
  - Example: OpenAI has "InferenceProvider" role in NEXUS ecosystem
  - Example: BOB has "OrchestratorRole" for Forvis Mazars
  
- **Disposition** = Intrinsic capability based on implementation
  - Example: ABI has "MultiLineDataCapability" (W3C SSE compliant)
  - Example: GPT-4o has "VisionCapability" (can process images)

---

## 3. Provider Compatibility Matrix (Ontology-Driven)

Using BFO classifications, we can reason about provider compatibility:

```turtle
# Example: ABI Provider Instance
:ABIForvisMazars a nexus:ABIProvider ;
    nexus:implementsProtocol nexus:W3C_SSE ;
    nexus:hasCapability :MultiLineDataCapability ;
    nexus:hasRole nexus:InferenceProvider ;
    nexus:providedBy :NaasAI .

# Example: OpenAI Provider Instance
:OpenAIChatGPT a nexus:OpenAIProvider ;
    nexus:implementsProtocol nexus:OpenAI_SSE ;
    nexus:hasCapability :SingleLineDataCapability ;
    nexus:hasCapability nexus:FunctionCallingCapability ;
    nexus:hasCapability nexus:VisionCapability ;
    nexus:hasRole nexus:InferenceProvider ;
    nexus:hasRole nexus:ToolProvider ;
    nexus:hasRole nexus:MultimodalProvider .

# Example: Anthropic Provider Instance
:AnthropicClaude a nexus:AnthropicProvider ;
    nexus:implementsProtocol nexus:Anthropic_SSE ;
    nexus:hasCapability :SingleLineDataCapability ;
    nexus:hasCapability :LifecycleEventsCapability ;
    nexus:hasCapability nexus:FunctionCallingCapability ;
    nexus:hasRole nexus:InferenceProvider ;
    nexus:hasRole nexus:ToolProvider .
```

**Reasoning Queries (SPARQL):**

```sparql
# Find all providers that support W3C SSE
SELECT ?provider WHERE {
    ?provider nexus:implementsProtocol nexus:W3C_SSE .
}

# Find providers with function calling capability
SELECT ?provider WHERE {
    ?provider nexus:hasCapability nexus:FunctionCallingCapability .
}

# Find providers that require multi-line data: parsing
SELECT ?provider WHERE {
    ?provider nexus:hasCapability nexus:MultiLineDataCapability .
}
```

---

## 4. Adapter Ontology

Adapters bridge between provider-specific protocols and NEXUS canonical format:

```turtle
nexus:ProviderAdapter a owl:Class ;
    rdfs:label "Provider Adapter"@en ;
    skos:definition "Software component that translates provider-specific streaming format to NEXUS canonical StreamEvent"@en ;
    nexus:hasRole nexus:AdapterRole .

nexus:OpenAIAdapter a owl:Class ;
    rdfs:subClassOf nexus:ProviderAdapter ;
    rdfs:label "OpenAI Adapter"@en ;
    nexus:handlesProtocol nexus:OpenAI_SSE ;
    nexus:producesEvent nexus:StreamEvent .

nexus:ABIAdapter a owl:Class ;
    rdfs:subClassOf nexus:ProviderAdapter ;
    rdfs:label "ABI Adapter"@en ;
    nexus:handlesProtocol nexus:W3C_SSE ;
    nexus:producesEvent nexus:StreamEvent ;
    skos:note "Must handle multiple data: lines per event"@en .

nexus:AnthropicAdapter a owl:Class ;
    rdfs:subClassOf nexus:ProviderAdapter ;
    rdfs:label "Anthropic Adapter"@en ;
    nexus:handlesProtocol nexus:Anthropic_SSE ;
    nexus:producesEvent nexus:StreamEvent ;
    skos:note "Maps lifecycle events to NEXUS event types"@en .

# Adapter Properties
nexus:handlesProtocol a owl:ObjectProperty ;
    rdfs:domain nexus:ProviderAdapter ;
    rdfs:range nexus:StreamingProtocol ;
    rdfs:label "handles protocol"@en .

nexus:producesEvent a owl:ObjectProperty ;
    rdfs:domain nexus:ProviderAdapter ;
    rdfs:range nexus:StreamEvent ;
    rdfs:label "produces event"@en .

nexus:adaptsProvider a owl:ObjectProperty ;
    rdfs:domain nexus:ProviderAdapter ;
    rdfs:range nexus:AIProvider ;
    rdfs:label "adapts provider"@en .
```

---

## 5. Complete BFO Alignment Table

| BFO Bucket | BFO Class | NEXUS Class | Purpose | Key Properties |
|------------|-----------|-------------|---------|----------------|
| **WHAT** | Process | `StreamEvent` | Discrete streaming events | `type`, `content`, `metadata` |
| | | `ContentEvent` | Text generation | `content`, `tokenCount` |
| | | `ThinkingEvent` | Reasoning display | `reasoning`, `duration` |
| | | `ToolCallEvent` | Function invocation | `toolName`, `arguments` |
| | | `FileEvent` | File/attachment | `url`, `filename`, `mimeType` |
| **WHEN** | Temporal Region | `StreamSequence` | Event ordering | `eventIndex`, `timestamp` |
| | | `StreamLifecycle` | Connection state | `phase` |
| **WHO** | Material Entity | `AIProvider` | Service provider | `name`, `endpoint` |
| | | `AIModel` | Neural network | `modelId`, `version` |
| | | `AIAgent` | Configured instance | `agentId`, `workspace` |
| **WHERE** | Site | `APIEndpoint` | Network location | `url`, `region` |
| | | `Workspace` | Logical boundary | `workspaceId`, `members` |
| **HOW WE KNOW** | Gen. Dependent Continuant | `StreamingProtocol` | Abstract spec | `name`, `version` |
| | | `W3C_SSE` | Standard SSE | `supportsMultiline: true` |
| | | `OpenAI_SSE` | Custom format | `supportsEventTypes: false` |
| **HOW IT IS** | Quality | `EventProperty` | Intrinsic attribute | `value`, `unit` |
| | | `Latency` | Response time | `milliseconds` |
| | | `TokenCount` | Content size | `tokens` |
| **WHY** | Role | `ProviderRole` | Social purpose | `capabilities` |
| | | `AgentRole` | Agent purpose | `specialization` |
| | Disposition | `StreamingCapability` | Technical ability | `enabled` |
| | | `MultiLineDataCapability` | W3C SSE support | `true/false` |

---

## 6. Implementation Specifications

### 6.1 Adapter Registry (Ontology-Driven)

```python
# apps/api/app/services/providers/registry.py

from typing import Type, Dict
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

NEXUS = Namespace("http://ontology.naas.ai/nexus/")
BFO = Namespace("http://purl.obolibrary.org/obo/")

class OntologyDrivenRegistry:
    """Provider adapter registry backed by BFO ontology"""
    
    def __init__(self):
        self.graph = Graph()
        self.graph.parse("/Users/jrvmac/nexus/docs/research/nexus_providers.ttl", format="turtle")
        self._adapters: Dict[str, Type[ProviderAdapter]] = {}
    
    def register_adapter(self, adapter_class: Type[ProviderAdapter]):
        """Register adapter and infer capabilities from ontology"""
        adapter_uri = NEXUS[adapter_class.__name__]
        
        # Query ontology for adapter capabilities
        query = f"""
        SELECT ?protocol ?capability WHERE {{
            <{adapter_uri}> nexus:handlesProtocol ?protocol .
            <{adapter_uri}> nexus:hasCapability ?capability .
        }}
        """
        
        results = self.graph.query(query)
        for row in results:
            protocol = row.protocol
            capability = row.capability
            # Store metadata for runtime decisions
            
        self._adapters[adapter_class.provider_type] = adapter_class
    
    def get_adapter_for_provider(self, provider: AIProvider) -> ProviderAdapter:
        """Select appropriate adapter based on provider's protocol"""
        
        # Query: Which adapter handles this provider's protocol?
        provider_uri = NEXUS[provider.id]
        query = f"""
        SELECT ?adapter WHERE {{
            <{provider_uri}> nexus:implementsProtocol ?protocol .
            ?adapter nexus:handlesProtocol ?protocol .
        }}
        """
        
        results = self.graph.query(query)
        # ... return matching adapter
    
    def validate_compatibility(self, provider: AIProvider, required_capabilities: list) -> bool:
        """Check if provider has required capabilities using ontology reasoning"""
        
        provider_uri = NEXUS[provider.id]
        
        for capability in required_capabilities:
            query = f"""
            ASK {{
                <{provider_uri}> nexus:hasCapability nexus:{capability} .
            }}
            """
            if not self.graph.query(query):
                return False
        
        return True
```

### 6.2 Event Validation (BFO-Constrained)

```python
# apps/api/app/services/providers/validation.py

class EventValidator:
    """Validate StreamEvents against BFO constraints"""
    
    def validate_event(self, event: StreamEvent, ontology: Graph) -> bool:
        """Ensure event satisfies BFO process constraints"""
        
        # BFO constraint: Process must have participant
        if not self._has_participant(event, ontology):
            raise ValidationError("StreamEvent must have participant (BFO_0000057)")
        
        # BFO constraint: Process must occupy temporal region
        if not event.timestamp:
            raise ValidationError("StreamEvent must have timestamp (BFO_0000199)")
        
        # NEXUS constraint: Event must have type
        if not event.type:
            raise ValidationError("StreamEvent must have type")
        
        # Format-specific validation
        if event.type == StreamEventType.LINK:
            if not self._is_valid_url(event.content):
                raise ValidationError("LinkEvent content must be valid URL")
        
        return True
    
    def validate_sequence(self, events: list[StreamEvent]) -> bool:
        """Ensure event sequence satisfies temporal constraints"""
        
        # BFO constraint: Temporal ordering (precedes relation)
        for i in range(len(events) - 1):
            if events[i].timestamp >= events[i+1].timestamp:
                raise ValidationError("Events must be temporally ordered (BFO_0000063)")
        
        # NEXUS constraint: DONE event must be last
        done_events = [e for e in events if e.type == StreamEventType.DONE]
        if done_events and done_events[0] != events[-1]:
            raise ValidationError("DoneEvent must be final event")
        
        return True
```

### 6.3 Protocol Detection (Ontology-Guided)

```python
# apps/api/app/services/providers/detection.py

class ProtocolDetector:
    """Detect streaming protocol from response characteristics"""
    
    def __init__(self, ontology: Graph):
        self.ontology = ontology
    
    def detect_protocol(self, response_headers: dict, sample_lines: list[str]) -> str:
        """Detect protocol and map to ontology class"""
        
        content_type = response_headers.get("content-type", "")
        
        # Check for SSE
        if "text/event-stream" not in content_type:
            return "unknown"
        
        has_event_lines = any(line.startswith("event: ") for line in sample_lines)
        has_data_lines = any(line.startswith("data: ") for line in sample_lines)
        
        if not has_data_lines:
            return "malformed"
        
        # Count data: lines per event block
        event_blocks = self._split_into_event_blocks(sample_lines)
        avg_data_per_event = sum(
            len([l for l in block if l.startswith("data: ")])
            for block in event_blocks
        ) / len(event_blocks) if event_blocks else 0
        
        # Classify protocol
        if has_event_lines and avg_data_per_event > 1.5:
            return "W3C_SSE"  # Multiple data: per event
        elif has_event_lines and avg_data_per_event <= 1.5:
            return "Anthropic_SSE"  # Event types, single data:
        elif not has_event_lines:
            # Check for OpenAI JSON format
            data_lines = [l[6:] for l in sample_lines if l.startswith("data: ")]
            if all(self._is_json(d) for d in data_lines[:3]):
                return "OpenAI_SSE"
        
        return "unknown"
    
    def get_adapter_for_protocol(self, protocol: str) -> str:
        """Map protocol to adapter class using ontology"""
        
        query = f"""
        SELECT ?adapter WHERE {{
            ?adapter nexus:handlesProtocol nexus:{protocol} .
        }}
        """
        
        results = self.ontology.query(query)
        # Return adapter class name
```

---

## 7. Testing Strategy (Ontology-Based)

### 7.1 Protocol Conformance Tests

```python
# tests/test_protocol_conformance.py

class TestProtocolConformance:
    """Test that providers conform to their declared protocols"""
    
    def test_abi_conforms_to_w3c_sse(self):
        """ABI must implement W3C SSE correctly"""
        
        adapter = ABIAdapter()
        provider = ABIProvider(endpoint="...", api_key="...")
        
        # Check ontology: Does ABI declare W3C_SSE?
        assert ontology.value(
            subject=NEXUS.ABIProvider,
            predicate=NEXUS.implementsProtocol,
            object=NEXUS.W3C_SSE
        )
        
        # Test multi-line data: support
        mock_response = """
event: ai_message
data: First line
data: Second line

data: [DONE]
"""
        events = list(adapter.parse_sse(mock_response))
        
        # Should concatenate multi-line data
        assert len(events) == 2
        assert "First line\nSecond line" in events[0].content
    
    def test_openai_conforms_to_custom_format(self):
        """OpenAI must implement its custom JSON format"""
        
        adapter = OpenAIAdapter()
        
        # Check ontology: Does OpenAI declare OpenAI_SSE?
        assert ontology.value(
            subject=NEXUS.OpenAIProvider,
            predicate=NEXUS.implementsProtocol,
            object=NEXUS.OpenAI_SSE
        )
        
        # Test single-line JSON
        mock_response = """
data: {"choices": [{"delta": {"content": "Hello"}}]}

data: [DONE]
"""
        events = list(adapter.parse_sse(mock_response))
        
        assert len(events) == 2
        assert events[0].content == "Hello"
```

### 7.2 Capability Tests

```python
# tests/test_capabilities.py

class TestProviderCapabilities:
    """Test that providers deliver on their declared capabilities"""
    
    def test_providers_with_function_calling_capability(self):
        """All providers claiming function calling must support it"""
        
        query = """
        SELECT ?provider WHERE {
            ?provider nexus:hasCapability nexus:FunctionCallingCapability .
        }
        """
        
        for row in ontology.query(query):
            provider = get_provider_instance(row.provider)
            adapter = get_adapter(provider)
            
            # Test function calling
            events = list(adapter.stream(
                messages=[...],
                tools=[{"name": "get_weather", "parameters": {...}}]
            ))
            
            # Must emit ToolCallEvent
            tool_calls = [e for e in events if e.type == StreamEventType.TOOL_CALL]
            assert len(tool_calls) > 0, f"{provider} claims FunctionCallingCapability but didn't emit ToolCallEvent"
```

---

## 8. Migration Path

### Phase 1: Ontology Definition (Week 1)
- [ ] Complete `nexus_providers.ttl` ontology file
- [ ] Define all BFO-aligned classes and properties
- [ ] Document provider instances with capabilities
- [ ] Set up RDFLib integration

### Phase 2: Adapter Refactoring (Week 2)
- [ ] Extract current streaming logic into adapter classes
- [ ] Implement `OntologyDrivenRegistry`
- [ ] Add protocol detection
- [ ] Validate against ontology constraints

### Phase 3: Validation & Testing (Week 3)
- [ ] Implement `EventValidator`
- [ ] Create protocol conformance test suite
- [ ] Test all 18 ABI agents + OpenAI + Anthropic
- [ ] Document gaps and edge cases

### Phase 4: Production Rollout (Week 4)
- [ ] Deploy ontology-driven adapter system
- [ ] Monitor streaming events for compliance
- [ ] Generate adapter coverage reports
- [ ] Create plugin system for new providers

---

## 9. Expected Outcomes

### 9.1 Interoperability
- **Any provider** can integrate by mapping to BFO ontology
- **Automated validation** ensures protocol compliance
- **Clear contracts** between NEXUS and providers

### 9.2 Extensibility
- **New providers** = define ontology instance + implement adapter
- **No core changes** required for new protocols
- **Plugin architecture** for community providers

### 9.3 Reasoning Capabilities
- **Query providers** by capability (e.g., "find all providers with vision")
- **Validate compatibility** before routing requests
- **Generate adapters** from ontology specs (future)

### 9.4 Standards Compliance
- **ISO 21383-2 (BFO)** alignment for scientific rigor
- **W3C SSE** support for standards-based providers
- **Industry patterns** (OpenAI, Anthropic) for pragmatic adoption

---

## 10. References

1. **BFO Specification:** https://github.com/BFO-ontology/BFO-2020
2. **ISO 21383-2:2024** - Basic Formal Ontology
3. **W3C SSE Specification:** https://html.spec.whatwg.org/multipage/server-sent-events.html
4. **OpenAI Streaming API:** https://platform.openai.com/docs/api-reference/chat-streaming
5. **Anthropic Streaming:** https://docs.anthropic.com/claude/reference/streaming
6. **NEXUS Documentation:**
   - `SSE_STREAMING_STANDARDS.md` - Protocol comparison
   - `ABI_INTEGRATION_GAPS.md` - ABI-specific gaps
   - `PROVIDER_ADAPTER_ARCHITECTURE.md` - Technical architecture

---

*Last Updated: 2026-02-09*  
*Status: Specification Draft v1.0*  
*Authors: NEXUS Platform Team, BFO Working Group*  
*Standard: ISO 21383-2 (Basic Formal Ontology)*

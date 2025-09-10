# DPROD SPARQL Query Examples

This document provides practical SPARQL query examples for discovering and analyzing AI agents using DPROD metadata in the ABI system.

## Setup

All queries assume the following prefixes:

```sparql
PREFIX dprod: <https://ekgf.github.io/dprod/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX abi: <https://abi.naas.ai/schema/>
PREFIX prov: <http://www.w3.org/ns/prov#>
```

## Agent Discovery Queries

### 1. List All Available Agents

```sparql
SELECT ?agent ?label ?description ?privacyLevel ?performanceTier
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  ?agent rdfs:comment ?description .
  ?agent abi:privacyLevel ?privacyLevel .
  ?agent abi:performanceTier ?performanceTier .
}
ORDER BY ?label
```

**Use Case**: Get an overview of all available AI agents in the system.

**Expected Results**:
```
| agent | label | description | privacyLevel | performanceTier |
|-------|-------|-------------|--------------|-----------------|
| https://abi.naas.ai/data-product/chatgpt | ChatGPT | OpenAI GPT-4o... | cloud | high |
| https://abi.naas.ai/data-product/claude | Claude | Anthropic Claude... | cloud | high |
| https://abi.naas.ai/data-product/qwen | Qwen | Local privacy-focused... | local | standard |
```

### 2. Find Agents by Capability

```sparql
SELECT ?agent ?label ?capabilities
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  ?agent abi:capabilities ?capabilities .
  FILTER(CONTAINS(?capabilities, "coding"))
}
ORDER BY ?label
```

**Use Case**: Find all agents capable of code generation and programming assistance.

### 3. Find Local (Privacy-Focused) Agents

```sparql
SELECT ?agent ?label ?modelName ?capabilities
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  ?agent abi:privacyLevel "local" .
  ?agent abi:modelInfo ?modelInfo .
  ?modelInfo abi:modelName ?modelName .
  ?agent abi:capabilities ?capabilities .
}
```

**Use Case**: Discover agents that run locally for privacy-sensitive tasks.

### 4. Find Best Agent for Specific Task

```sparql
SELECT ?agent ?label ?score
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  ?agent abi:capabilities ?cap .
  ?agent abi:performanceTier ?tier .
  
  # Looking for reasoning capabilities
  FILTER(CONTAINS(?cap, "reasoning"))
  
  # Score based on performance tier
  BIND(
    IF(?tier = "high", 3,
    IF(?tier = "medium", 2, 1)) AS ?score
  )
}
ORDER BY DESC(?score)
LIMIT 3
```

**Use Case**: Find the best agents for complex reasoning tasks, ranked by performance.

## Agent Metadata Queries

### 5. Get Detailed Agent Information

```sparql
SELECT ?agent ?label ?modelName ?contextWindow ?temperature ?languages
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  ?agent abi:modelInfo ?modelInfo .
  ?modelInfo abi:modelName ?modelName .
  ?modelInfo abi:contextWindow ?contextWindow .
  ?modelInfo abi:temperature ?temperature .
  ?agent abi:supportedLanguages ?languages .
}
```

**Use Case**: Get technical details about agent models and configurations.

### 6. Compare Agent Performance Characteristics

```sparql
SELECT ?agent ?label ?tier ?privacyLevel ?availability ?contextWindow
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  ?agent abi:performanceTier ?tier .
  ?agent abi:privacyLevel ?privacyLevel .
  ?agent abi:availability ?availability .
  ?agent abi:modelInfo ?modelInfo .
  ?modelInfo abi:contextWindow ?contextWindow .
}
ORDER BY ?tier DESC, ?contextWindow DESC
```

**Use Case**: Compare agents across multiple performance and capability dimensions.

## Observability Queries

### 7. Get Agent Usage Metrics

```sparql
SELECT ?agent ?timestamp ?responseTime ?tokenUsage ?success
WHERE {
  ?observability a abi:ObservabilityLog .
  ?observability abi:agent ?agent .
  ?observability abi:timestamp ?timestamp .
  ?observability abi:metrics ?metrics .
  ?metrics abi:responseTimeMs ?responseTime .
  ?metrics abi:tokenUsage ?tokenUsage .
  ?metrics abi:success ?success .
  
  # Filter for recent data (last 24 hours)
  FILTER(?timestamp > "2025-01-03T00:00:00Z"^^xsd:dateTime)
}
ORDER BY ?timestamp DESC
```

**Use Case**: Monitor agent performance and usage patterns.

### 8. Find Agents with Performance Issues

```sparql
SELECT ?agent ?avgResponseTime ?errorRate
WHERE {
  {
    SELECT ?agent (AVG(?responseTime) AS ?avgResponseTime)
    WHERE {
      ?observability a abi:ObservabilityLog .
      ?observability abi:agent ?agent .
      ?observability abi:metrics ?metrics .
      ?metrics abi:responseTimeMs ?responseTime .
      
      # Last hour
      FILTER(?timestamp > "2025-01-04T14:00:00Z"^^xsd:dateTime)
    }
    GROUP BY ?agent
  }
  
  {
    SELECT ?agent ((?failures / ?total) AS ?errorRate)
    WHERE {
      {
        SELECT ?agent (COUNT(*) AS ?total)
        WHERE {
          ?observability a abi:ObservabilityLog .
          ?observability abi:agent ?agent .
        }
        GROUP BY ?agent
      }
      
      {
        SELECT ?agent (COUNT(*) AS ?failures)
        WHERE {
          ?observability a abi:ObservabilityLog .
          ?observability abi:agent ?agent .
          ?observability abi:metrics ?metrics .
          ?metrics abi:success false .
        }
        GROUP BY ?agent
      }
    }
  }
  
  # Alert on slow response times or high error rates
  FILTER(?avgResponseTime > 5000 || ?errorRate > 0.05)
}
```

**Use Case**: Identify agents experiencing performance or reliability issues.

## Conversation Lineage Queries

### 9. Trace Conversation Flow

```sparql
SELECT ?step ?fromAgent ?toAgent ?timestamp ?activity
WHERE {
  ?conversation abi:conversationId "conv-12345" .
  ?conversation prov:hadStep ?step .
  ?step prov:used ?fromAgent .
  ?step prov:generated ?toAgent .
  ?step prov:atTime ?timestamp .
  ?step prov:wasAssociatedWith ?activity .
}
ORDER BY ?timestamp
```

**Use Case**: Understand how a conversation flowed between different agents.

### 10. Find Most Common Agent Transitions

```sparql
SELECT ?fromAgent ?toAgent (COUNT(*) AS ?transitionCount)
WHERE {
  ?step prov:used ?fromAgent .
  ?step prov:generated ?toAgent .
  ?step prov:atTime ?timestamp .
  
  # Last week
  FILTER(?timestamp > "2024-12-28T00:00:00Z"^^xsd:dateTime)
}
GROUP BY ?fromAgent ?toAgent
ORDER BY DESC(?transitionCount)
LIMIT 10
```

**Use Case**: Analyze common conversation patterns and agent handoff flows.

## Data Quality and Compliance Queries

### 11. Validate Agent Metadata Completeness

```sparql
SELECT ?agent ?label ?missingFields
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  
  # Check for required fields
  OPTIONAL { ?agent rdfs:comment ?description }
  OPTIONAL { ?agent abi:capabilities ?capabilities }
  OPTIONAL { ?agent abi:modelInfo ?modelInfo }
  OPTIONAL { ?agent abi:performanceTier ?tier }
  
  # Build list of missing fields
  BIND(
    CONCAT(
      IF(!BOUND(?description), "description ", ""),
      IF(!BOUND(?capabilities), "capabilities ", ""),
      IF(!BOUND(?modelInfo), "modelInfo ", ""),
      IF(!BOUND(?tier), "performanceTier ", "")
    ) AS ?missingFields
  )
  
  # Only show agents with missing fields
  FILTER(?missingFields != "")
}
```

**Use Case**: Identify agents with incomplete DPROD metadata for data quality improvement.

### 12. Check DPROD Compliance

```sparql
SELECT ?agent ?label ?complianceLevel
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  
  # Check for DPROD required elements
  OPTIONAL { ?agent dprod:inputPort ?inputPort }
  OPTIONAL { ?agent dprod:outputPort ?outputPort }
  OPTIONAL { ?agent dcat:landingPage ?landingPage }
  OPTIONAL { ?agent dcterms:publisher ?publisher }
  
  # Calculate compliance score
  BIND(
    (IF(BOUND(?inputPort), 1, 0) +
     IF(BOUND(?outputPort), 1, 0) +
     IF(BOUND(?landingPage), 1, 0) +
     IF(BOUND(?publisher), 1, 0)) AS ?score
  )
  
  BIND(
    IF(?score = 4, "Full",
    IF(?score >= 2, "Partial", "Minimal")) AS ?complianceLevel
  )
}
ORDER BY ?score DESC
```

**Use Case**: Assess DPROD specification compliance across all agents.

## Advanced Analytics Queries

### 13. Agent Popularity and Usage Trends

```sparql
SELECT ?agent ?label ?usageCount ?avgResponseTime ?successRate
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  
  {
    SELECT ?agent (COUNT(*) AS ?usageCount)
    WHERE {
      ?observability a abi:ObservabilityLog .
      ?observability abi:agent ?agent .
      ?observability abi:timestamp ?timestamp .
      
      # Last 7 days
      FILTER(?timestamp > "2024-12-28T00:00:00Z"^^xsd:dateTime)
    }
    GROUP BY ?agent
  }
  
  {
    SELECT ?agent (AVG(?responseTime) AS ?avgResponseTime)
    WHERE {
      ?observability a abi:ObservabilityLog .
      ?observability abi:agent ?agent .
      ?observability abi:metrics ?metrics .
      ?metrics abi:responseTimeMs ?responseTime .
    }
    GROUP BY ?agent
  }
  
  {
    SELECT ?agent (AVG(IF(?success, 1.0, 0.0)) AS ?successRate)
    WHERE {
      ?observability a abi:ObservabilityLog .
      ?observability abi:agent ?agent .
      ?observability abi:metrics ?metrics .
      ?metrics abi:success ?success .
    }
    GROUP BY ?agent
  }
}
ORDER BY DESC(?usageCount)
```

**Use Case**: Analyze agent popularity, performance, and reliability for optimization decisions.

### 14. Capability Coverage Analysis

```sparql
SELECT ?capability (COUNT(DISTINCT ?agent) AS ?agentCount) ?agents
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  ?agent abi:capabilities ?capabilities .
  
  # Extract individual capabilities (assuming comma-separated)
  # Note: This is simplified - real implementation would need string splitting
  BIND(?capabilities AS ?capability)
  
  # Group agents by capability
  GROUP_CONCAT(?label; separator=", ") AS ?agents
}
GROUP BY ?capability
ORDER BY DESC(?agentCount)
```

**Use Case**: Understand capability coverage and identify gaps in agent portfolio.

## Query Examples for Integration

### 15. Export Agent Catalog for External Systems

```sparql
CONSTRUCT {
  ?agent a dprod:DataProduct ;
    rdfs:label ?label ;
    rdfs:comment ?description ;
    dprod:inputPort ?inputPort ;
    dprod:outputPort ?outputPort ;
    abi:capabilities ?capabilities ;
    abi:modelInfo ?modelInfo ;
    dcat:landingPage ?landingPage .
}
WHERE {
  ?agent a dprod:DataProduct .
  ?agent rdfs:label ?label .
  ?agent rdfs:comment ?description .
  ?agent dprod:inputPort ?inputPort .
  ?agent dprod:outputPort ?outputPort .
  ?agent abi:capabilities ?capabilities .
  ?agent abi:modelInfo ?modelInfo .
  ?agent dcat:landingPage ?landingPage .
}
```

**Use Case**: Generate DPROD-compliant RDF for export to enterprise data catalogs.

These queries demonstrate the power of DPROD for making AI agents discoverable, analyzable, and manageable through standard semantic web technologies.
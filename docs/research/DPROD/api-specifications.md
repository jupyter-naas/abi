# DPROD API Specifications

## Overview

This document defines the API specifications for interacting with DPROD-compliant data in the ABI system. These APIs enable enterprise systems to discover agents, query metadata, track lineage, and monitor performance using standard DPROD formats.

## Base Configuration

**Base URL**: `https://api.abi.naas.ai/v1/dprod`
**Authentication**: Bearer token (OAuth 2.0 / API Key)
**Content-Type**: `application/json` or `application/ld+json`

## Agent Discovery APIs

### List All Data Products (Agents)

**Endpoint**: `GET /data-products`

**Description**: Retrieve all AI agents as DPROD-compliant data products.

**Query Parameters**:
- `category` (optional): Filter by category (`cloud`, `local`, `utility`)
- `capability` (optional): Filter by capability (e.g., `coding`, `reasoning`)
- `privacy_level` (optional): Filter by privacy level (`local`, `cloud`)
- `performance_tier` (optional): Filter by performance (`high`, `medium`, `standard`)
- `format` (optional): Response format (`json`, `jsonld`, `turtle`, `rdf-xml`)

**Example Request**:
```http
GET /v1/dprod/data-products?capability=coding&privacy_level=local&format=jsonld
Authorization: Bearer your-api-token
```

**Example Response**:
```json
{
  "@context": "https://ekgf.github.io/dprod/dprod.jsonld",
  "dataProducts": [
    {
      "id": "https://abi.naas.ai/data-product/qwen",
      "type": "DataProduct",
      "label": "Qwen Local AI Agent",
      "description": "Privacy-focused multilingual AI agent via Ollama",
      "abi:capabilities": ["coding", "multilingual", "reasoning"],
      "abi:privacyLevel": "local",
      "abi:performanceTier": "standard",
      "inputPort": {
        "id": "https://abi.naas.ai/data-product/qwen/input",
        "type": "DataService",
        "endpointURL": "https://api.naas.ai/agents/qwen/chat"
      },
      "outputPort": [
        {
          "id": "https://abi.naas.ai/data-product/qwen/output",
          "type": "DataService"
        }
      ]
    }
  ],
  "totalCount": 1,
  "page": 1,
  "pageSize": 50
}
```

### Get Specific Data Product

**Endpoint**: `GET /data-products/{agent-name}`

**Description**: Retrieve detailed DPROD metadata for a specific agent.

**Path Parameters**:
- `agent-name`: Name of the agent (e.g., `qwen`, `chatgpt`, `claude`)

**Example Request**:
```http
GET /v1/dprod/data-products/qwen
Authorization: Bearer your-api-token
```

## Agent Discovery & Selection APIs

### Find Agents by Capability

**Endpoint**: `POST /agents/discover`

**Description**: Discover agents using semantic queries based on capabilities and requirements.

**Request Body**:
```json
{
  "requirements": {
    "capabilities": ["coding", "reasoning"],
    "privacyLevel": "local",
    "maxResponseTime": 3000,
    "languages": ["en", "zh"]
  },
  "ranking": {
    "criteria": ["performance", "privacy", "cost"],
    "weights": [0.4, 0.4, 0.2]
  },
  "limit": 5
}
```

**Example Response**:
```json
{
  "recommendations": [
    {
      "agent": "https://abi.naas.ai/data-product/qwen",
      "label": "Qwen Local AI Agent",
      "score": 0.92,
      "reasoning": "High privacy (local), supports coding and reasoning, multilingual",
      "matchedCapabilities": ["coding", "reasoning"],
      "estimatedResponseTime": 1200
    },
    {
      "agent": "https://abi.naas.ai/data-product/deepseek",
      "label": "DeepSeek R1 Agent",
      "score": 0.87,
      "reasoning": "Local deployment, excellent reasoning capabilities",
      "matchedCapabilities": ["reasoning"],
      "estimatedResponseTime": 1800
    }
  ],
  "totalFound": 2
}
```

## SPARQL Query API

### Execute SPARQL Query

**Endpoint**: `POST /sparql`

**Description**: Execute SPARQL queries against the DPROD knowledge graph.

**Request Body**:
```json
{
  "query": "PREFIX dprod: <https://ekgf.github.io/dprod/> PREFIX abi: <https://abi.naas.ai/schema/> SELECT ?agent ?label ?capabilities WHERE { ?agent a dprod:DataProduct . ?agent rdfs:label ?label . ?agent abi:capabilities ?capabilities . FILTER(CONTAINS(?capabilities, \"coding\")) }",
  "format": "json",
  "reasoning": true
}
```

**Example Response**:
```json
{
  "head": {
    "vars": ["agent", "label", "capabilities"]
  },
  "results": {
    "bindings": [
      {
        "agent": {
          "type": "uri",
          "value": "https://abi.naas.ai/data-product/qwen"
        },
        "label": {
          "type": "literal",
          "value": "Qwen Local AI Agent"
        },
        "capabilities": {
          "type": "literal", 
          "value": "coding,multilingual,reasoning"
        }
      }
    ]
  },
  "executionTime": 47
}
```

### Predefined Query Templates

**Endpoint**: `GET /sparql/templates`

**Description**: Get predefined SPARQL query templates for common use cases.

**Example Response**:
```json
{
  "templates": [
    {
      "id": "find-by-capability",
      "name": "Find Agents by Capability",
      "description": "Find agents with specific capabilities",
      "query": "PREFIX dprod: <https://ekgf.github.io/dprod/> SELECT ?agent ?label WHERE { ?agent a dprod:DataProduct . ?agent rdfs:label ?label . ?agent abi:capabilities ?cap . FILTER(CONTAINS(?cap, \"{{capability}}\")) }",
      "parameters": [
        {
          "name": "capability",
          "type": "string",
          "description": "Required capability (e.g., coding, reasoning)"
        }
      ]
    }
  ]
}
```

## Observability APIs

### Get Agent Metrics

**Endpoint**: `GET /observability/{agent-name}`

**Description**: Retrieve observability data for a specific agent.

**Path Parameters**:
- `agent-name`: Name of the agent

**Query Parameters**:
- `start_time`: Start time (ISO 8601)
- `end_time`: End time (ISO 8601)
- `metrics`: Comma-separated list of metrics (`response_time`, `token_usage`, `success_rate`)
- `aggregation`: Aggregation level (`raw`, `hourly`, `daily`)

**Example Request**:
```http
GET /v1/dprod/observability/qwen?start_time=2025-01-04T00:00:00Z&end_time=2025-01-04T23:59:59Z&metrics=response_time,success_rate&aggregation=hourly
```

**Example Response**:
```json
{
  "@context": "https://ekgf.github.io/dprod/dprod.jsonld",
  "agent": "https://abi.naas.ai/data-product/qwen",
  "timeWindow": {
    "start": "2025-01-04T00:00:00Z",
    "end": "2025-01-04T23:59:59Z",
    "aggregation": "hourly"
  },
  "metrics": [
    {
      "timestamp": "2025-01-04T15:00:00Z",
      "responseTimeMs": {
        "avg": 1247.5,
        "min": 456.2,
        "max": 3421.8,
        "p95": 2156.7
      },
      "successRate": 0.984,
      "requestCount": 127
    }
  ],
  "conformsTo": "https://abi.naas.ai/schema/AgentObservability"
}
```

### System Performance Dashboard

**Endpoint**: `GET /observability/dashboard`

**Description**: Get system-wide performance metrics and analytics.

**Example Response**:
```json
{
  "systemMetrics": {
    "totalAgents": 13,
    "activeAgents": 11,
    "totalRequests24h": 1247,
    "avgSystemResponseTime": 1756.3,
    "overallSuccessRate": 0.987
  },
  "topAgents": [
    {
      "agent": "chatgpt",
      "requests": 203,
      "avgResponseTime": 1789.2,
      "successRate": 0.995
    },
    {
      "agent": "qwen", 
      "requests": 127,
      "avgResponseTime": 1156.7,
      "successRate": 0.984
    }
  ],
  "capabilityUsage": {
    "coding": 34.2,
    "analysis": 23.1,
    "general": 19.4,
    "creative": 12.8,
    "research": 10.5
  }
}
```

## Lineage Tracking APIs

### Get Conversation Lineage

**Endpoint**: `GET /lineage/conversations/{conversation-id}`

**Description**: Retrieve the complete lineage for a conversation showing agent handoffs and data flow.

**Path Parameters**:
- `conversation-id`: Unique conversation identifier

**Example Response**:
```json
{
  "@context": [
    "https://ekgf.github.io/dprod/dprod.jsonld",
    {"prov": "http://www.w3.org/ns/prov#"}
  ],
  "conversationId": "conv-12345",
  "startTime": "2025-01-04T15:30:00Z",
  "endTime": "2025-01-04T15:32:15Z",
  "steps": [
    {
      "stepNumber": 1,
      "activity": "initial_routing",
      "from": "user",
      "to": "abi",
      "timestamp": "2025-01-04T15:30:00Z",
      "duration": "PT2S"
    },
    {
      "stepNumber": 2,
      "activity": "agent_execution", 
      "from": "abi",
      "to": "qwen",
      "timestamp": "2025-01-04T15:30:02Z",
      "duration": "PT43S",
      "reason": "local_privacy_preferred"
    }
  ],
  "summary": {
    "totalSteps": 4,
    "agentsUsed": ["abi", "qwen", "claude"],
    "totalDuration": "PT2M15S"
  }
}
```

### Agent Transition Analytics

**Endpoint**: `GET /lineage/transitions`

**Description**: Analyze common agent transition patterns across conversations.

**Query Parameters**:
- `start_date`: Start date for analysis
- `end_date`: End date for analysis
- `min_occurrences`: Minimum occurrences to include

**Example Response**:
```json
{
  "transitions": [
    {
      "from": "abi",
      "to": "chatgpt",
      "count": 78,
      "percentage": 31.2,
      "avgDuration": "PT45S",
      "successRate": 0.995
    },
    {
      "from": "abi", 
      "to": "qwen",
      "count": 45,
      "percentage": 18.0,
      "avgDuration": "PT38S",
      "successRate": 0.984
    }
  ],
  "totalTransitions": 250,
  "analysisWindow": "P7D"
}
```

## Data Catalog Integration APIs

### Export for Enterprise Catalogs

**Endpoint**: `GET /export/{format}`

**Description**: Export agent metadata in enterprise data catalog formats.

**Path Parameters**:
- `format`: Export format (`datahub`, `purview`, `collibra`, `atlas`)

**Query Parameters**:
- `agents`: Comma-separated list of agents to export (optional, defaults to all)
- `include_observability`: Include observability metadata (default: false)

**Example Request**:
```http
GET /v1/dprod/export/datahub?agents=qwen,chatgpt&include_observability=true
```

### Webhook Registration

**Endpoint**: `POST /webhooks`

**Description**: Register webhooks for real-time notifications of metadata changes.

**Request Body**:
```json
{
  "url": "https://your-system.com/webhooks/abi-metadata",
  "events": ["agent_registered", "metadata_updated", "performance_alert"],
  "filters": {
    "agents": ["qwen", "chatgpt"],
    "metrics": ["response_time", "success_rate"]
  },
  "auth": {
    "type": "bearer",
    "token": "your-webhook-token"
  }
}
```

## Authentication & Security

### API Key Management

**Endpoint**: `POST /auth/keys`

**Description**: Generate API keys with specific permissions.

**Request Body**:
```json
{
  "name": "Enterprise Data Catalog Integration",
  "permissions": [
    "dprod:read",
    "sparql:execute", 
    "observability:read",
    "lineage:read"
  ],
  "expiresAt": "2026-01-04T00:00:00Z",
  "ipWhitelist": ["10.0.0.0/8", "192.168.1.100"]
}
```

### Rate Limiting

All APIs are subject to rate limiting:
- **Standard**: 1000 requests/hour
- **Premium**: 10000 requests/hour  
- **Enterprise**: Custom limits

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1641024000
```

## Error Handling

### Standard Error Response

```json
{
  "error": {
    "code": "INVALID_QUERY",
    "message": "SPARQL query syntax error at line 2",
    "details": {
      "line": 2,
      "column": 15,
      "suggestion": "Missing closing quote"
    },
    "timestamp": "2025-01-04T15:30:45Z",
    "requestId": "req-12345"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_QUERY` | 400 | Malformed SPARQL query |
| `AGENT_NOT_FOUND` | 404 | Requested agent does not exist |
| `UNAUTHORIZED` | 401 | Invalid or missing authentication |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

---

These APIs provide comprehensive access to DPROD-compliant data while maintaining enterprise-grade security and performance standards.
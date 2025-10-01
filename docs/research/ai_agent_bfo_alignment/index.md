# BFO 7-Bucket AI Agent Ontology Alignment

Complete documentation of the BFO-compliant AI agent ontology restructuring project.

## Contents

1. **[README.md](./README.md)** - Complete technical summary
   - Executive summary of the 7-bucket BFO alignment
   - What was accomplished
   - Technical verification
   - Critical discoveries (module loading bug)
   - Next steps

2. **[ai-agent-queries.md](./ai-agent-queries.md)** - SPARQL Query System
   - Templatable SPARQL queries for AI agent ontology
   - Query definitions and examples
   - BFO-compliant query patterns
   - Integration with ABI agent
   - Testing procedures

## Quick Start

### Understanding the 7-Bucket Structure

All 7 AI agent ontologies follow this BFO structure:

| Bucket | BFO Class | Example |
|--------|-----------|---------|
| **1** | Material Entity | Server infrastructure |
| **2** | Quality | Accuracy, precision |
| **3** | Realizable Entity | Capabilities |
| **4** | Process | Web search, reasoning |
| **5** | Immaterial Entity | Data center regions |
| **6** | Temporal Region | Processing sessions |
| **7** | Generically Dependent Continuant | AI agents, models, prompts |

### Querying Agent Data

```sparql
PREFIX abi: <http://ontology.naas.ai/abi/>
SELECT ?agent_name ?model_name ?context_window
WHERE {
  ?agent a abi:AIAgent ;
         rdfs:label ?agent_name ;
         abi:usesModel ?model .
  ?model rdfs:label ?model_name ;
         abi:hasContextWindow ?context_window .
}
ORDER BY DESC(?context_window)
```

### Files Referenced

**Ontologies:**
- `src/core/chatgpt/ontologies/ChatgptOntology.ttl` (124 lines)
- `src/core/claude/ontologies/ClaudeOntology.ttl` (124 lines)
- `src/core/grok/ontologies/GrokOntology.ttl` (124 lines)
- `src/core/perplexity/ontologies/PerplexityOntology.ttl` (124 lines)
- `src/core/mistral/ontologies/MistralOntology.ttl` (124 lines)
- `src/core/gemini/ontologies/GeminiOntology.ttl` (124 lines)
- `src/core/deepseek/ontologies/DeepseekOntology.ttl` (124 lines)

**Queries:**
- `src/core/abi/ontologies/domain-level/AIAgentQueries.ttl`
- `src/core/abi/ontologies/application-level/AgentRecommendationQueries.ttl`

**Base Ontology:**
- `src/core/abi/ontologies/domain-level/AIAgentOntology.ttl`

## Branch

`BFO-example` - All commits pushed to origin

## Status

✅ **Complete and verified** - Ready for review and merge

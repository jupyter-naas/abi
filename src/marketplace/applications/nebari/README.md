# Nebari Module

## Overview

### Description

The Nebari Module provides comprehensive expertise on the Nebari open-source data science platform, specializing in cloud infrastructure, Kubernetes orchestration, and collaborative data science workflows.

This module enables:
- Expert guidance on Nebari deployment and architecture
- Data science infrastructure best practices
- Cloud-agnostic scaling and cost optimization
- Security, governance, and compliance guidance
- Community support and ecosystem integration

### Requirements

**Cloud Mode (Recommended):**
- OpenAI API key configured in environment
- Set `AI_MODE=cloud` in your configuration

**Local Mode:**
- Ollama installed with Qwen3:8b model
- Set `AI_MODE=local` in your configuration

### TL;DR

To get started with the Nebari module:

1. Configure your AI mode (cloud or local)
2. Ensure proper API keys or local model setup

Start chatting using this command:
```bash
make chat agent=Nebari
```

### Structure

```
src/marketplace/applications/nebari/

├── agents/                         
│   ├── NebariAgent_test.py               
│   └── NebariAgent.py          
├── models/                         
│   ├── gpt_4_1.py                
│   └── qwen3_8b.py                
├── ontologies/                     
│   ├── NebariOntology.ttl            
│   └── NebariSparqlQueries.ttl                          
├── __init__.py
└── README.md                       
```

## Core Components

### Agents

#### Nebari Agent
Expert Nebari platform agent specializing in data science infrastructure, deployment, and collaboration workflows.

**Capabilities:**
- Comprehensive Q&A covering 7 domains (35+ intents)
- Architecture and deployment guidance
- Security and compliance expertise
- Performance optimization recommendations
- Community support and ecosystem integration

**Use Cases:**
- Enterprise data science platform deployment
- Cloud infrastructure architecture decisions
- Security and governance configuration
- Performance scaling and cost optimization
- Team collaboration and workflow setup

#### Testing
```bash
uv run python -m pytest src/marketplace/applications/nebari/agents/NebariAgent_test.py
```

**Test Coverage:**
- Agent name and identity verification
- Intent matching for core Q&A scenarios
- Model integration (cloud/local modes)
- Tool functionality validation

### Models

#### GPT-4.1 (Cloud Mode)
- **Model ID:** gpt-4.1
- **Context Window:** 1,047,576 tokens
- **Owner:** OpenAI
- **Description:** Excels at instruction following and tool calling with broad domain knowledge

#### Qwen3:8b (Local Mode)
- **Model ID:** qwen3:8b
- **Context Window:** 32,768 tokens
- **Owner:** Alibaba
- **Description:** Privacy-focused local model for multi-agent orchestration

### Ontologies

#### Nebari Ontology
Turtle ontology defining Nebari-specific classes and properties for semantic knowledge representation.

#### Nebari SPARQL Queries
Turtle file containing templatable SPARQL queries for ontology-based class searching and knowledge retrieval.

## Dependencies

### Python Libraries
- `abi.services.agent`: Agent framework and intent handling
- `langchain_core`: Tool integration for AI agents
- `langchain_openai`: LangChain OpenAI integration (cloud mode)
- `langchain_ollama`: LangChain Ollama integration (local mode)
- `pydantic`: Data validation and serialization

### Core Dependencies
- `src.core.templatablesparqlquery`: SPARQL query templating system
- `src.secret`: Configuration and secret management
- `typing`: Type hints and optional parameters

### External Services
- **OpenAI API** (cloud mode): GPT-4.1 model access
- **Ollama** (local mode): Qwen3:8b model execution
- **Kubernetes**: Target deployment platform for Nebari
- **Terraform**: Infrastructure provisioning
- **Helm**: Application deployment

## Q&A Knowledge Base

The Nebari agent includes comprehensive Q&A coverage across 7 critical domains:

### 1. General & High Level (6 intents)
- Platform overview and value propositions
- Target audience and licensing
- Community maintenance and core benefits

### 2. Architecture & Deployment (6 intents)
- Terraform, Kubernetes, and Helm architecture
- Cloud platform support (AWS, Azure, GCP)
- Deployment processes and prerequisites

### 3. Features & Functionality (5 intents)
- Integrated tools (JupyterHub, Dask, conda-store)
- Collaboration and GPU support
- Monitoring and observability

### 4. Use Cases & Workflows (5 intents)
- Enterprise platforms and research hubs
- ML workflow support and team collaboration
- User onboarding and access patterns

### 5. Compatibility & Ecosystem (5 intents)
- Open-source component integration
- External system connectivity
- Extension mechanisms and cloud neutrality

### 6. Performance & Cost (5 intents)
- Computational scaling and cost optimization
- HPC workload support and monitoring tools
- Resource management and efficiency

### 7. Security & Governance (5 intents)
- Authentication methods and user isolation
- RBAC and compliance standards
- Logging and activity monitoring

### 8. Community & Support (5 intents)
- Community channels and update cycles
- Documentation and enterprise support
- Contribution guidelines and resources
# ABI Installation & Configuration

**ABI** (Agentic Brain Infrastructure) is an AI Network development framework. The open source platform enables intelligent, multi-agent systems that run on servers and cloud infrastructure, with mobile and edge deployment under research. Your entire AI Network is defined in a single configuration file.

## What is ABI?

**Key Benefits:**
- **Configuration-Driven** - Define your entire AI Network in a single file
- **Zero Code Changes** - Modify agent behavior through configuration
- **Intelligent Routing** - Commands automatically reach the right agents
- **Complete Memory** - Knowledge graphs, SQL databases, and vector storage
- **Portable** - Run on servers and cloud, with mobile/edge research underway
- **Open Source** - Complete transparency and open to community contributions

## When to Use ABI

**Use ABI when you need:**
- Custom AI agents for specific processes
- Local and cloud deployment capabilities
- Local data processing for sensitive information
- Full control over AI models and deployment
- Development environment for platform integrations

**Use the Naas.ai cloud platform when you need:**
- Quick start without setup
- Team collaboration and sharing
- Managed infrastructure and scaling

Most users start with the cloud platform and add ABI for customization later.

## Portable Deployment

Deploy the same configuration across different devices and environments:

**Development**
- Develop and test locally on your machine
- Full control over data and processing
- Offline capabilities

**Cloud Infrastructure**  
- Deploy to cloud servers for scaling
- Leverage cloud compute for heavy workloads
- Integrate with cloud services

**Mobile and Edge Devices** *(Research Stage)*
- Exploring deployment on phones, tablets, and IoT devices
- Research into distributed processing at the network edge
- Future capability to bring AI closer to users

The same configuration file works everywhere.

## Prerequisites

Before installing ABI, ensure you have:

- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** - Required for Oxigraph triple store, Dagster, and PostgreSQL
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** - Python package manager
- **Python 3.11+** - For running ABI components
- **Git** - For cloning repositories

## Installation Options

Choose the approach that best fits your needs:

### 1. Clone Repository (Recommended)
Best for: Exploring ABI and following tutorials

```bash
git clone https://github.com/jupyter-naas/abi.git
cd abi
```

### 2. Fork Repository
Best for: Contributing back to the project

```bash
# 1. Fork via GitHub UI: https://github.com/jupyter-naas/abi/fork
# 2. Clone your fork
git clone https://github.com/YOUR-USERNAME/abi.git
cd abi
```

### 3. Private Fork
Best for: Private customization with upstream sync

```bash
# 1. Create private repository via GitHub UI
# 2. Clone your private repository
git clone https://github.com/YOUR-USERNAME/abi-private.git
cd abi-private

# 3. Add upstream for updates
git remote add upstream https://github.com/jupyter-naas/abi.git
git pull --rebase upstream main
git push
```

## Environment Setup

### 1. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your preferred editor and configure at least one AI model provider:

```bash
# OpenAI (recommended for getting started)
OPENAI_API_KEY=sk-your-openai-api-key

# Anthropic Claude
ANTHROPIC_API_KEY=your-anthropic-api-key

# Google Gemini  
GOOGLE_API_KEY=your-google-api-key

# Mistral
MISTRAL_API_KEY=your-mistral-api-key
```

**Note:** The .env file should never be committed to version control as it contains sensitive credentials.

### 2. Configure AI Network

ABI uses a single `config.yaml` file to define your AI Network. The main sections include:

**System Configuration:**
- `workspace_id`: Naas Platform workspace ID for storage and publishing
- `github_project_repository`: Your GitHub repository (e.g. "jupyter-naas/abi")
- `api_title`: API title displayed in documentation
- `storage_name` and `space_name`: Storage configuration

**AI Network Configuration:**
The `ai_network` section defines your agents:

```yaml
ai_network:
  # ABI Orchestrator with centralized intent mapping
  abi:
    enabled: true
    description: "Multi-agent orchestrator"
    strengths: "Orchestration, strategic advisory"
    use_when: "Identity, strategy, coordination"
    intent_mapping:
      raw_intents:
        "what is your name": "My name is ABI"
        "who are you": "I am ABI, developed by NaasAI"
      tool_intents:
        open_knowledge_graph_explorer:
          - "show knowledge graph"
          - "sparql query"
        check_ai_network_config:
          - "list agents"
          - "agent status"
      agent_intents:
        chatgpt:
          - "use chatgpt"
          - "web search"
        claude:
          - "use claude"
          - "anthropic"

  # Foundation AI Models
  chatgpt:
    enabled: true
    description: "OpenAI ChatGPT"
    strengths: "General conversation, coding"
    use_when: "General tasks, coding help"

  claude:
    enabled: true
    description: "Anthropic Claude"
    strengths: "Analysis, writing"
    use_when: "Detailed analysis"

  # Disabled agents (ready for activation)
  llama:
    enabled: false
    description: "Meta Llama"
    strengths: "Local, private"
    use_when: "Private tasks"
```

## Configuration-Driven Architecture

ABI uses a single configuration file to define your AI Network:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor': '#f8fafc', 'primaryTextColor': '#1e293b', 'primaryBorderColor': '#e2e8f0', 'lineColor': '#64748b'}}}%%
graph TB
    User["User Input<br/>'use claude for analysis'"] --> ABI["ABI Orchestrator<br/>Intent Routing"]
    
    ABI --> Claude["Claude Agent<br/>Analysis & Writing"]
    ABI --> ChatGPT["ChatGPT Agent<br/>General & Coding"]
    ABI --> Gemini["Gemini Agent<br/>Multimodal"]
    ABI --> Tools["Tools<br/>Knowledge Graph Explorer<br/>Config Check"]
    
    Config["config.yaml<br/>• Agent definitions<br/>• Intent mappings<br/>• Enable/disable"] -.-> ABI
    
    subgraph "Memory Services"
        KG["Knowledge Graph<br/>Triple Store<br/>Ontologies & Relations"]
        SQL["SQL Database<br/>Structured Data<br/>Agent Memory"]
        Vector["Vector Store<br/>Embeddings<br/>(Coming Soon)"]
    end
    
    Claude <--> KG
    Claude <--> SQL
    Claude <--> Vector
    ChatGPT <--> KG
    ChatGPT <--> SQL
    ChatGPT <--> Vector
    Gemini <--> KG
    Gemini <--> SQL
    Gemini <--> Vector
    Tools <--> KG
    Tools <--> SQL
    Tools <--> Vector
    
    Claude --> Response1["Analysis with<br/>contextual knowledge"]
    ChatGPT --> Response2["Code with<br/>learned patterns"]
    Gemini --> Response3["Multimodal with<br/>memory context"]
    Tools --> Response4["System info with<br/>historical data"]
    
    %% Standard class definitions
    classDef userExp fill:#e8f5e8,stroke:#4caf50,stroke-width:2px,color:#2e7d32
    classDef platform fill:#e3f2fd,stroke:#2196f3,stroke-width:1px,color:#1565c0
    classDef aiEngine fill:#fff3e0,stroke:#ff9800,stroke-width:2px,color:#e65100
    classDef dataLayer fill:#f3e5f5,stroke:#9c27b0,stroke-width:1px,color:#4a148c
    classDef infrastructure fill:#fce4ec,stroke:#e91e63,stroke-width:1px,color:#880e4f
    
    %% Apply classes to nodes
    class User userExp
    class ABI platform
    class Claude,ChatGPT,Gemini aiEngine
    class Tools platform
    class Config infrastructure
    class KG,SQL,Vector dataLayer
    class Response1,Response2,Response3,Response4 userExp
```

- **Single Source**: Your entire AI Network in one config.yaml file
- **Intelligent Routing**: Commands automatically reach the appropriate agents
- **Intent Mapping**: Support for direct responses, tool routing, and agent routing
- **Memory Services**: Knowledge graphs, SQL databases, and vector storage for context
- **Agent Control**: Enable/disable agents with a config change
- **No Code Changes**: Modify behavior through configuration

### Agent Definition Structure

Each agent contains:
- **enabled**: Boolean flag for activation
- **description**: Brief agent description
- **strengths**: Core capabilities
- **use_when**: Recommended use cases

### ABI Intent Mapping Types

The ABI agent contains centralized intent mapping with three types:
- **raw_intents**: Direct text responses (key-value pairs)
- **tool_intents**: Route to specific tools/functions
- **agent_intents**: Route to specific agents

**Benefits:**
- **Agent Control**: Change `enabled: true/false` to activate/deactivate agents
- **Configuration-Based**: All agent behavior controlled through config.yaml
- **Consistent Management**: Unified agent identification across your AI Network
- **Dynamic Mapping**: Add new intents and behaviors through configuration

## Quick Start

### Start Your First Agent

Once configured, start ABI:

```bash
make
```

Here's what happens in your terminal:

```
$ make

  _____ _____ _____ _____
 |     |     |     |     |
 |  C  |  O  |  R  |  E  |
 |_____|_____|_____|_____|

🔍 Running code quality checks...

📝 Linting with ruff...
All checks passed!

🔍 Running static type analysis...
Success: no issues found in 173 source files

✅ CORE security checks passed!

🚀 Starting ABI Agent...
🐳 Starting Docker services...
   - Oxigraph triple store (port 7878)
   - PostgreSQL database (port 5432)
   - Dagster orchestration (port 3000)

🧠 Initializing knowledge graph...
📊 Loading 7 AI agents: abi, chatgpt, gemini, claude, mistral, perplexity, grok

💬 ABI Agent ready! Type your message below:

ABI: Hello! I'm your ABI agent. I can help you with building custom AI agents, 
managing knowledge graphs, and orchestrating multi-agent workflows.

What would you like to work on today?

You: use claude for analysis
ABI: Transferring to Claude for detailed analysis...

Claude: I'm Claude, ready to help with thoughtful analysis and writing tasks. 
What would you like me to analyze?

You: 
```

The first run takes a few minutes to download Docker containers and initialize services.

## Verification

### Test Core Functionality

Try these commands to verify your installation:

```bash
# Test agent interaction
echo "What agents are available?" | make chat-abi-agent-prompt

# Test API server (in another terminal)
make api
# Then visit http://localhost:8000/docs

# Check services are running
docker ps
```

You should see containers running for:
- Oxigraph (port 7878) - Knowledge graph triple store
- PostgreSQL (port 5432) - Agent memory and structured data
- Dagster (port 3000) - Workflow orchestration

## Troubleshooting

### Common Issues

**Docker not running?**
```bash
# Start Docker Desktop and verify
docker --version
docker ps
```

**Python dependencies failing?**
```bash
# Ensure uv is installed and updated
uv --version
uv self update

# Clean and reinstall
rm -rf .venv
make setup
```

**Oxigraph connection errors?**
```bash
# Check if container is running
docker ps | grep oxigraph

# Restart if needed
docker-compose down
docker-compose up -d oxigraph
```

**Agent not responding?**
```bash
# Check environment variables
cat .env | grep API_KEY

# Verify API key validity
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

## Next Steps

Now that ABI is installed, explore its capabilities:

### Explore Built-in Agents
```bash
# Chat with different specialized agents
make chat-growth-agent
make chat-finance-agent  
make chat-content-agent
```

### Learn the System
- **Explore the knowledge graph**: `make chat-ontology-agent`
- **Build custom agents**: Follow our agent development guides
- **Add integrations**: Connect to external services
- **Create workflows**: Automate complex processes

### Development Tools

ABI includes comprehensive development tools:

```bash
# Core functionality
make chat-abi-agent          # Main agent interface
make api                     # Start API server
make setup                   # Install dependencies

# Development
make lint                    # Code linting
make format                  # Code formatting
make test                    # Run test suite

# Ontology management
make ontology-update         # Update knowledge graph
make ontology-backup         # Backup ontologies
```

## Getting Help

**Documentation:**
- [ABI Repository](https://github.com/jupyter-naas/abi) - Full documentation
- [Agent Development](https://github.com/jupyter-naas/abi/docs) - Creating custom agents

**Community Support:**
- [GitHub Discussions](https://github.com/jupyter-naas/abi/discussions) - Community Q&A
- [GitHub Issues](https://github.com/jupyter-naas/abi/issues) - Bug reports and feature requests

**Direct Support:**
- Email: support@naas.ai

## Updating ABI

Keep your ABI installation current:

### Regular Updates
```bash
# Pull latest changes
git pull origin main

# Update dependencies
make setup

# Restart services
make chat-abi-agent
```

### For Private Forks
```bash
# Sync with upstream
git fetch upstream
git rebase upstream/main
git push origin main

# Update dependencies
make setup
```

Your ABI installation is now ready! Start building custom AI solutions with complete configuration-driven flexibility.

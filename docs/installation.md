# ABI Installation & Configuration

**ABI** (Agentic Brain Infrastructure) is your AI Network development framework - the open source core that powers intelligent, multi-agent systems with seamless deployment across local, cloud, and edge environments. ABI provides a configuration-driven platform where your entire AI Network is defined in a single `config.yaml` file, enabling you to build once and deploy anywhere with zero code changes.

## What is ABI?

**Key Benefits:**
- 🔧 **Configuration-Driven** - Your entire AI Network defined in config.yaml with SLUG-based routing
- 🔄 **Zero Code Changes** - Enable/disable agents and modify behavior through configuration only
- 🎯 **Enhanced Intent Mapping** - Support for RAW, TOOL, and AGENT intent types
- 🌐 **Seamless Deployment** - Build once, deploy anywhere: local → cloud → edge with zero friction
- 🔄 **Environment Agnostic** - Same config.yaml works across all deployment targets
- 🔬 **Edge Computing Ready** - Research-backed edge deployment capabilities
- 🚀 **Open Source** - Complete transparency and community contributions
- 🤖 **Multi-Agent** - Orchestrate multiple specialized AI agents seamlessly

## When to Use ABI

**✅ Use ABI When You Need:**
- Configuration-driven AI Network with instant agent activation
- Seamless deployment across local, cloud, and edge environments
- Custom AI agents for specific business processes
- Build once, deploy anywhere capability
- Local data processing for sensitive information
- Deep customization of AI behavior through config.yaml
- Edge computing capabilities for distributed AI
- Environment-agnostic AI Network management
- Full control over AI models and data
- Development environment for building platform integrations

**🌐 Use Cloud Platform When You Need:**
- Quick start without any setup
- Team collaboration and sharing
- Managed infrastructure and scaling
- Browser-based interface for non-technical users
- Immediate productivity with pre-built agents

Most users start with the cloud platform and add ABI for customization later.

## Seamless Multi-Environment Deployment

ABI's revolutionary architecture enables effortless transitions between deployment environments:

**🏠 Local Development**
- Develop and test your AI Network locally
- Full control over data and processing
- Offline capabilities for sensitive workflows

**☁️ Cloud Scaling**  
- Deploy the same config.yaml to cloud infrastructure
- Leverage cloud compute for heavy workloads
- Integrate with cloud services seamlessly

**⚡ Edge Computing**
- Push AI capabilities to edge devices
- Research-backed edge deployment (coming soon)
- Distributed AI processing at the network edge

**🔄 Zero-Friction Migration**
- Same configuration file works everywhere
- No code changes between environments
- Seamless agent orchestration across deployment targets

## Prerequisites

Before installing ABI, ensure you have:

- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** - Required for Oxigraph triple store
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

ABI's revolutionary approach uses a single `config.yaml` file to define your entire AI Network. This configuration-driven architecture eliminates hardcoded agents and enables instant modifications. The main sections include:

**System Configuration:**
- `workspace_id`: Naas Platform workspace ID for storage and publishing
- `github_project_repository`: Your GitHub repository (e.g. "jupyter-naas/abi")
- `api_title`: API title displayed in documentation
- `storage_name` and `space_name`: Storage configuration

**AI Network Configuration:**
The `ai_network` section is where the magic happens - define all your agents using SLUG-based identifiers with instant enable/disable capability:

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

## Revolutionary Configuration-Driven Architecture

ABI's breakthrough configuration system transforms how AI Networks are built and managed:

- **Single Source of Truth**: Your entire AI Network defined in one config.yaml file
- **SLUG-Based Routing**: Consistent agent identification and routing system
- **Enhanced Intent Mapping**: Revolutionary support for RAW, TOOL, and AGENT intent types
- **Instant Agent Control**: Enable/disable agents with a single config change
- **Zero Code Modifications**: All behavior changes through configuration only
- **Complete Flexibility**: Add new agents and intents without touching code

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

**Revolutionary Benefits:**
- **Instant Agent Control**: Simply change `enabled: true/false` to activate/deactivate any agent
- **Zero Code Modifications**: All agent behavior and intent routing controlled through config.yaml
- **SLUG-Based Routing**: Consistent agent identification across your entire AI Network
- **Dynamic Intent Mapping**: Add new intents and behaviors without touching a single line of code

## Quick Start

### Start Your First Agent

Once configured, start chatting with the core ABI agent:

```bash
make chat-abi-agent
```

This command will:
1. Set up the environment and install Python dependencies
2. Start Docker services (Oxigraph triple store)
3. Initialize the knowledge graph with base ontologies
4. Launch the interactive agent in your terminal

The first run may take a few minutes as it downloads and starts the Oxigraph Docker container.

### Expected Output

You should see something like:

```
🚀 Starting ABI Agent...
🐳 Starting Oxigraph triple store...
🧠 Initializing knowledge graph...
💬 ABI Agent ready! Type your message below:

ABI Agent: Hello! I'm your ABI agent. I can help you with:
- Building custom AI agents
- Managing ontologies and knowledge graphs  
- Creating integrations with external services
- Developing workflows and pipelines

What would you like to work on today?

You: 
```

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

You should see the Oxigraph container running on port 7878.

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

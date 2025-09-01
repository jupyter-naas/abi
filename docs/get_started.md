# Get Started

**Table of Contents**

- [Get Started](#get-started)
  - [Introduction](#introduction)
    - [What is ABI?](#what-is-abi)
    - [Why ABI?](#why-abi)
    - [Key Features](#key-features)
    - [Key Capabilities](#key-capabilities)
  - [Installation](#installation)
    - [Pre-requisites](#pre-requisites)
    - [Installation Options](#installation-options)
    - [Setup Environment](#setup-environment)
    - [Configure YAML](#configure-yaml)
  - [Quickstart](#quickstart)
    - [Start Chatting](#start-chatting)
  - [Help \& Support](#help--support)

## Introduction

### What is ABI?

**ABI** (Agentic Brain Infrastructure) is your local AI development framework - the open source core that powers intelligent, multi-agent systems. ABI provides a configuration-driven platform for building, customizing, and orchestrating AI agents tailored to your specific needs.

**Key Benefits:**
- 🔧 **Customize Everything** - Build custom agents for specific business processes
- 🏠 **Run Locally** - Keep sensitive data on your infrastructure  
- ⚙️ **Full Control** - Modify, extend, and integrate however you want
- 🚀 **Open Source** - Complete transparency and community contributions
- 🤖 **Multi-Agent** - Orchestrate multiple specialized AI agents seamlessly

### Why ABI?

ABI provides an open alternative to monolithic AI solutions by emphasizing modularity and customization. Unlike rigid platforms, ABI's configuration-driven architecture allows organizations to:

- **Start Simple**: Begin with basic agents and expand as needed
- **Stay Flexible**: Change agent behavior through configuration, not code
- **Scale Intelligently**: Add new agents and capabilities without system rewrites
- **Maintain Control**: Keep your AI infrastructure and data under your control

Combined with the Naas.ai ecosystem, ABI serves as the brain of your organization's agentic AI applications.

### When to Use ABI

**✅ Use ABI When You Need:**
- Custom AI agents for specific business processes
- Local data processing for sensitive information
- Deep customization of AI behavior and tools
- Offline capabilities without internet dependency
- Full control over AI models and data
- Development environment for building platform integrations

**🌐 Use Cloud Platform When You Need:**
- Quick start without any setup
- Team collaboration and sharing
- Managed infrastructure and scaling
- Browser-based interface for non-technical users
- Immediate productivity with pre-built agents

Most users start with the cloud platform and add ABI for customization later.

### Key Features

- **Configuration-Driven Agents**: All agents defined in config.yaml with SLUG-based routing
- **Enhanced Intent Mapping**: Support for RAW, TOOL, and AGENT intent types
- **Dynamic Agent Loading**: Enable/disable agents without code changes
- **Multi-Model Support**: Built-in support for OpenAI, Anthropic, Google, Meta, and Mistral
- **Ontology-Based Knowledge**: Convert data into knowledge using flexible ontology system
- **Flexible Storage**: Manage unstructured data, knowledge graphs, and vector data seamlessly
- **Customizable API**: Deploy all components via API for external integration

### Key Capabilities

- **Event-Driven**: Actions can be triggered by events logged in the triple store.
- **Deterministic Queries**: Deterministic SPARQL queries can be added to the ontology to used by the agents as tools without having to create any python code.
- **Scheduling Tasks**: Tasks can be pre-processed and scheduled to avoid latency.
- **Multi-models**: This project is model agnostic with built-in support for major LLM providers including OpenAI, Anthropic, Google, Meta, and Mistral. You can use any LLM you want in your agents or workflows.

## Installation

Get started with ABI - Install, configure and chat with your first agent.

### Pre-requisites

- **Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)** - Required for running Oxigraph and other services
- **Install [uv](https://docs.astral.sh/uv/getting-started/installation/)** - Python package manager
- **Create your account on [NAAS](https://naas.ai)** (Optional, only if you want to use the storage system in production)

### Installation Options

Choose one of the following options:

1. **Clone the Repository**
```bash
git clone https://github.com/jupyter-naas/abi.git
cd abi
```

2. **Fork the Repository**
```bash
# 1. Fork via GitHub UI
# 2. Clone your fork
git clone https://github.com/YOUR-USERNAME/abi.git
cd abi
```

3. **Create a Private Fork**
```bash
# 1. Create private repository via GitHub UI
# 2. Clone your private repository
git clone https://github.com/YOUR-USERNAME/abi-private.git
cd abi-private
git remote add upstream https://github.com/jupyter-naas/abi.git
git pull --rebase upstream main
git push
```

### Setup Environment

1. Copy this file to .env
```bash
cp .env.example .env
```
2. Replace placeholder values with your actual credentials
3. Uncomment (remove #) from lines you want to activate. The variables are used to configure the assistant.

**Available AI Models**: ABI supports multiple LLM providers. Configure the API keys for the models you want to use:
- `OPENAI_API_KEY` - For GPT-4o and Llama 3.3 70B models
- `ANTHROPIC_API_KEY` - For Claude 3.5 Sonnet model
- `GOOGLE_API_KEY` - For Gemini 2.0 Flash model
- `MISTRAL_API_KEY` - For Mistral Large 2 model

Note: The .env file should never be committed to version control
as it contains sensitive credentials

### Configure YAML

ABI uses a single `config.yaml` file for all configuration. The main configuration includes:

**System Configuration:**
- `workspace_id`: Naas Platform workspace ID for storage and publishing
- `github_project_repository`: Your GitHub repository (e.g. "jupyter-naas/abi")
- `github_support_repository`: Repository for support issues
- `github_project_id`: GitHub project number for issue assignment
- `triple_store_path`: Path to ontology store (e.g. "storage/triplestore")
- `api_title`: API title displayed in documentation
- `api_description`: API description for documentation
- `storage_name` and `space_name`: Storage configuration

**AI Network Configuration:**
The `ai_network` section defines all your agents using SLUG-based identifiers:

```yaml
ai_network:
  abi:
    enabled: true
    description: "Multi-agent orchestrator"
    strengths: "Orchestration, strategic advisory"
    use_when: "Identity, strategy, coordination"
    intent_mapping:
      # Raw responses, tool routing, and agent routing
      
  chatgpt:
    enabled: true
    description: "OpenAI ChatGPT"
    strengths: "General conversation, coding"
    use_when: "General tasks, coding help"
    
  claude:
    enabled: false  # Easily enable/disable agents
    description: "Anthropic Claude"
    strengths: "Analysis, writing"
    use_when: "Detailed analysis"
```

**Key Benefits:**
- **Instant Agent Control**: Change `enabled: true/false` to activate/deactivate agents
- **Zero Code Changes**: All agent behavior controlled through configuration
- **SLUG-Based Routing**: Consistent agent identification across the system

## Quickstart

### Start Chatting

Now, the project is installed and configured, you can start chatting with the core agent by running the following command:

```bash
make chat-abi-agent
```

This command will:
1. Setup the environment and install dependencies
2. Initialize your .env configuration 
3. Start the Oxigraph triple store automatically (via Docker)
4. Initialize your knowledge graph
5. Run the Abi agent

It can take a few minutes the first time you run it as it needs to download and start the Oxigraph Docker container (though Oxigraph starts much faster than alternatives).

## Help & Support
For any questions or support requests, please create an issue on this repository or reach out via [support@naas.ai](mailto:support@naas.ai).



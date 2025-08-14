# ABI
*Agentic Brain Infrastructure*

**Version:** ABI-OS1 Beta 

> An organizational multi-agent system that uses ontologies to unify data, AI models, and workflows. 
⭐ **Star and follow to stay updated!**

## Overview

The **ABI** (Agentic Brain Infrastructure) project is a Python-based AI Operating System designed to serve as the core infrastructure for building an Agentic AI Ontology Engine. This system empowers organizations to integrate, manage, and scale AI-driven operations with multiple AI models (LLMs, SLMs, and other AI models), focusing on ontology, agent-driven workflows, and analytics. 

Built with international standards and regulatory frameworks as guiding principles, including [ISO/IEC 42001:2023 (AI Management Systems)](https://www.iso.org/standard/42001), [ISO/IEC 21838-2:2021 (Basic Formal Ontology)](https://www.iso.org/standard/74572.html), and forward-compatibility with emerging regulations like the EU AI Act, ABI provides a customizable framework suitable for individuals and organizations aiming to create intelligent, automated systems aligned to their needs.

## Why ABI?
The **ABI** project aims to provide a open alternative to Palantir by offering a flexible and scalable framework for building intelligent systems using ontology. Unlike Palantir, which is often seen as a monolithic solution, ABI emphasizes modularity and customization, allowing organizations to tailor their AI-driven operations to specific needs. Combined with the Naas.ai ecosystem, ABI can be used to build the brain of your organization's agentic AI applications.

## Key Features

- **Agents**: Configurable AI agents powered by multiple AI models (ChatGPT, Claude, Gemini, Grok, Llama, Mistral) to handle specific organizational tasks and interact with users.
- **Ontology Management**: Define and manage data relationships, structures, and semantic elements.
- **Integrations**: Seamlessly connect to external data sources and APIs for unified data access.
- **Pipelines**: Define data processing pipelines to handle and transform data efficiently into the ontological layer.
- **Workflows**: Automate complex business processes and manage end-to-end workflows.
- **Analytics**: Access insights through integrated analytics and real-time data processing.
- **Data**: Handle diverse datasets and manage schema, versioning, deduplication, and change data capture.

## Quick Start

**Step 1: Clone the repository**

```bash
git clone https://github.com/jupyter-naas/abi.git
cd abi
```

**Step 2: Setup environment variables**

```bash
cp .env.example .env
# Add your API keys for the AI models you want to use:
# OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, 
# MISTRAL_API_KEY, XAI_API_KEY (for Grok)
```

**Step 3: Run the project**

To run ABI with the Abi agent, which intelligently routes requests across all available AI models:

```bash
make
```

To run a specific agent:

```bash
make chat-[name]-agent
```

For example, to run the Abi agent or specific AI model agents:

```bash
make chat-abi-agent  # Smart routing across all AI models
make chat-chatgpt-agent     # GPT-4o
make chat-claude-agent      # Claude 3.5 Sonnet
make chat-grok-agent        # Grok-4 Latest
```

**Step 4: Build and run the API**

You need to build the API before running it. Find out more about the API in the [API documentation](./docs/api/deploy-api.md).

```bash
make api
```

## Research & Development

ABI is developed as part of ongoing applied research collaboration between:

- **[Naas](https://naas.ai)** - Applied Research Lab focused on creating universal data & AI platform that can connect the needs of individuals and organizations
- **[University at Buffalo](https://www.buffalo.edu/)** - Research university providing academic foundation and institutional support
- **[National Center for Ontological Research (NCOR)](https://ncor.buffalo.edu/)** - Leading research center for ontological foundations and formal knowledge representation
- **[Forvis Mazars](https://www.forvismazars.com/)** - Global audit and consulting firm providing governance and risk management expertise

This collaborative effort aims to better manage and control the way we use AI in society, ensuring responsible development and deployment of agentic AI systems through rigorous research, international standards compliance, and professional oversight.

## Funding & Support

ABI development is supported through:

- **Applied Research Grants** - Funding for ontological AI research and development
- **Academic Partnership** - University at Buffalo research collaboration and institutional support
- **Industry Partnerships** - Strategic partnerships including OpenTeams, Quansight, Forvis Mazars, VSquared AI, and other enterprise collaborators
- **Open Source Community** - Community contributions and collaborative development

*For funding opportunities, research partnerships, or enterprise support, contact us at support@naas.ai*

## Contributing

We welcome contributions! Please read the [contributing guidelines](./CONTRIBUTING.md) for more information.

## License
ABI Framework is open-source and available for use under the [MIT license](https://opensource.org/licenses/MIT). Professionals and enterprises are encouraged to contact our support for custom services as this project evolves rapidly at support@naas.ai


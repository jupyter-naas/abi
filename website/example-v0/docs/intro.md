# Welcome to ABI Platform

ABI (Agentic Brain Infrastructure) is a powerful platform for building custom AI assistants with domain expertise.

## Getting Started

- **[Chat Interface](/chat)** - Interact with ABI directly through our chat interface
- **[GitHub Repository](https://github.com/jupyter-naas/abi)** - Explore the source code and contribute

## Key Features

- 🧠 **Domain Experts** - 20+ specialized AI agents (Content Creator, Data Engineer, etc.)
- 🔗 **Enterprise Integration** - Connect to GitHub, Google, LinkedIn, databases  
- ⚡ **Multi-Model Power** - GPT-4, Claude, Gemini, Grok, Llama, and more
- 🏗️ **Custom Configuration** - Build AI that understands your specific workflows

## Architecture

ABI uses a modular architecture with:
- Semantic knowledge graphs for reasoning
- Ontology-driven workflows
- Multi-agent orchestration
- Enterprise-grade security

## API Integration

ABI provides a FastAPI backend that automatically exposes registered agents as API endpoints:

```bash
curl -X POST "http://localhost:9879/agents/abi/completion" \
  -H "Authorization: Bearer abi" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your question here", "thread_id": 1}'
```

Ready to interact with ABI? Try the [Chat Interface](/chat)!
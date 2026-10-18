---
sidebar_position: 2
---

# Marketplace

## Overview

The Marketplace is the `naas-abi-marketplace` package: a registry of ready-made modules that extend the ABI engine. It is part of the ABI repository, so a module is reviewed, tested and released with the framework.

## What is in it

| Category | Path | Contents |
|---|---|---|
| AI providers | `naas_abi_marketplace/ai/` | One module per provider (OpenRouter, Ollama, Anthropic, OpenAI, Gemini, Mistral, Bedrock, and more). Each registers its models in the model registry |
| Applications | `naas_abi_marketplace/applications/` | Integrations with third-party services (GitHub, Gmail, Notion, Postgres, Slack, Salesforce, and many more), each with an integration wrapper, an agent and an ontology |
| Domains | `naas_abi_marketplace/domains/` | Domain-expert agents, workflows, pipelines and ontologies, filed by the function they serve in an organization |
| Demos | `naas_abi_marketplace/__demo__/` | Reference implementations to copy from |

Browse the directories, or the `AGENTS.md` of each category, for the full list. Every module has the same shape as a module you write yourself: an `ABIModule` with its `dependencies` and a typed `Configuration`, and the optional folders `agents/`, `models/`, `integrations/`, `workflows/`, `pipelines/` and `ontologies/`. See [Creating a Module](/user-guide/build/modules/creating-a-module).

These are in-engine modules: the engine loads them from the `naas_abi_marketplace` package. To use one, see [Installing from the Marketplace](/user-guide/build/modules/marketplace/marketplace-install).

## Best Practices

When creating a module for the Marketplace:

1. **Self-contained design**: declare what the module needs in `ModuleDependencies`, and minimize its dependencies on other modules.
2. **Typed configuration**: put every setting in `Configuration(ModuleConfiguration)`, with a docstring that shows the `config.yaml` entry.
3. **Clear documentation**: a README with setup, configuration and examples.
4. **Tests**: `<Name>Agent_test.py` next to each agent, and an `on_load_test.py` that checks the module loads with a minimal configuration.
5. **Standard structure**: follow the layout and the `PascalCase.py` naming of the existing modules.
6. **Optional dependencies as extras**: a module that needs third-party libraries adds an extra to the package's `pyproject.toml`.

## Contributing to the Marketplace

To share a module with everyone, contribute it to the ABI repository: see [Publishing to the Marketplace](/user-guide/build/modules/marketplace/marketplace-publish). To keep a module private or ship it from your own repository, keep it in your project's `src/`, or create a [remote module](/user-guide/build/sdk/build-a-remote-module) as a repository of its own (`abi new module <name> --standalone`).

For questions or support, reach out via [support@naas.ai](mailto:support@naas.ai).

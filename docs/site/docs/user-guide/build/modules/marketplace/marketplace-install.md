---
sidebar_position: 1
---

# Installing from the Marketplace

The Marketplace is the `naas-abi-marketplace` package, which `naas-abi` already depends on. A module of it is a Python package under `naas_abi_marketplace`, so using one takes three steps: install its dependencies, enable it in `config.yaml`, restart the engine.

## 1. Install the module's dependencies

Each module is an optional extra, named `<category>-<module>`. Some extras are empty (the module needs nothing more); others pull the module's third-party libraries:

```bash
uv add "naas-abi-marketplace[applications-github]"
uv add "naas-abi-marketplace[ai-ollama]"
```

The extras are listed in `libs/naas-abi-marketplace/pyproject.toml` and in the package's `README.md`. A project created with `abi new project` already has the OpenRouter module enabled (`ai-openrouter` needs no extra).

## 2. Enable it in `config.yaml`

Add the module under `modules:` by its import path, with the settings its `Configuration` class declares (the class's docstring has an example). Secrets are written as `{{ secret.NAME }}`, and the value goes in `.env`:

```yaml
modules:
  - module: naas_abi_marketplace.applications.github
    enabled: true
    config:
      github_access_token: "{{ secret.GITHUB_ACCESS_TOKEN }}"
```

```bash
echo 'GITHUB_ACCESS_TOKEN=ghp_...' >> .env
```

The modules a module depends on (an AI provider, for instance) are loaded automatically; you do not list them. `abi module list` prints the modules of your configuration and whether each is enabled.

| Category | Path | What it adds |
|---|---|---|
| AI providers | `naas_abi_marketplace.ai.<provider>` | Models for the model registry (and a conversational agent) |
| Applications | `naas_abi_marketplace.applications.<app>` | An integration with a third-party service, and an agent that uses it |
| Domains | `naas_abi_marketplace.domains.<bucket>...` | Domain-expert agents, workflows and ontologies |

## 3. Restart and use it

Restart the engine (`abi dev down` then `abi dev up`, or `abi stack stop` then `abi stack start`). The module's agents appear in Nexus and in the API's `/agents` routes, its ontologies are loaded into the knowledge graph, and its workflows and pipelines are available as tools. You can try an agent from a terminal:

```bash
abi chat naas_abi_marketplace.applications.github GitHubAgent
```

The Nexus Marketplace page lists the installed modules and the catalog.

## Customizing a module

To change a Marketplace module, copy its package into your project's `src/` (for example `cp -r libs/naas-abi-marketplace/naas_abi_marketplace/applications/github src/my_github`), update the import paths inside the copy (the package imports itself by its full path), set `module: my_github` in `config.yaml`, and edit your copy. It is then an ordinary [in-engine module](/user-guide/build/modules/creating-a-module).

## Disabling a module

Set `enabled: false` on its entry in `config.yaml`, or remove the entry, and restart the engine.

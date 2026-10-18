---
sidebar_position: 10
---

# Publish Remote Agents

This page describes `scripts/publish_remote_agents.py`, a script of the ABI repository that publishes ABI agents as **remote plugins** in a Naas workspace. It is only useful with access to the Naas platform.

:::warning The script does not run in the current tree
`scripts/publish_remote_agents.py` imports `config` and `load_modules` from `naas_abi`, and `naas_abi.__modules__`. None of them exists in `naas-abi` 3.0: `python scripts/publish_remote_agents.py` (and so `make publish-remote-agents`) stops with an `ImportError`. This page describes what the script does, so you can judge whether to port it. Until it is ported, publish an agent by creating the plugin in the Naas workspace by hand, with the URL below.
:::

:::note Not the same as remote modules
A *remote plugin* is a Naas workspace entry that calls an agent of your API over HTTP. It has nothing to do with [remote modules](/user-guide/build/sdk/build-a-remote-module), the modules built with `naas-abi-sdk` that run in their own process and reach the engine over NATS.
:::

## What gets published

Every ABI agent is served by the API at `/agents/<route_name>/completion` and `/agents/<route_name>/stream-completion` (the route name comes from the agent's `as_api` method). A remote plugin points a Naas workspace at the streaming route of one agent:

```text
https://<space_name>-api.default.space.naas.ai/agents/<route_name>/stream-completion?token=<ABI_API_KEY>
```

For each agent, the script builds a plugin with:

- `id` and `slug`: the agent's name, lower-cased, with spaces and underscores replaced by `-`; `name`: the agent's name with underscores replaced by spaces;
- `description`, and `prompt` (the system prompt of the agent's configuration, `prompt_type: "system"`);
- `avatar` and `suggestions`, from the `AVATAR_URL` and `SUGGESTIONS` of the agent's module;
- `model: "gpt-4o"` and `temperature: 0`;
- `type`: `CORE`, `CUSTOM` or `DOMAIN`, from the module path;
- `default`: true for the agent named as the default;
- `remote.url`: the URL above.

## What the script does

1. Connects to the Naas platform with `NAAS_API_KEY` and lists the plugins of the workspace.
2. With `GITHUB_ACCESS_TOKEN` and a repository name, creates or updates the `ABI_API_KEY` secret of that GitHub repository.
3. Loads the agents of the enabled modules, and keeps the ones to publish: with `auto_publish.enabled`, every agent except `auto_publish.exclude_agents`; otherwise the script's own list of agents, which is empty as the script is written, so every agent is published.
4. For each one, updates the plugin of the same `id`, or creates it.
5. Marks the agent named by `auto_publish.default_agent` (default `Abi`) as the workspace's default.

## Configuration it expects

Environment (`.env`):

```bash
NAAS_API_KEY=...
ABI_API_KEY=...
GITHUB_ACCESS_TOKEN=...
```

Settings it reads from the engine's configuration, as attributes: `workspace_id` and `space_name` (the repository's `config.yaml` keeps these under its `deploy:` block, with `naas_api_key` and `env`), `github_repository`, and an optional `auto_publish` block:

```yaml
auto_publish:
  enabled: true
  default_agent: "Abi"
  exclude_agents:
    - "SomeExperimentalAgent"
```

The API base URL is built from `space_name`: `https://<space_name>-api.default.space.naas.ai`. A missing `NAAS_API_KEY`, `ABI_API_KEY` or workspace id stops the script with a `ValueError`; so does an agent without a route, with `Route name not found for agent <name>`.

## Preview first

`--dry-run` (also `--dryrun` and `-n`) logs the plugins it would create or update, and creates or updates nothing on Naas or GitHub:

```bash
uv run python scripts/publish_remote_agents.py --dry-run
make publish-remote-agents-dry-run
```

`make publish-remote-agents` runs the script for real. See [The Makefile](/developer-guide/toolchain/makefile#documentation-and-publishing).

## Security

- The plugin URL carries `ABI_API_KEY` as the `token` query parameter. Anyone who can read the plugin can call your API as that key: restrict who can see the workspace, and rotate the key when someone leaves.
- Use a GitHub token that can only write the secrets of the one repository.
- Keep every key out of version control. See [Add secrets to production](/user-guide/deploy/add_secrets_to_production).

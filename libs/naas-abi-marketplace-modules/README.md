# naas-abi-marketplace-modules

The marketplace application modules (`naas_abi_marketplace.applications.*`)
ported to **remote modules** ([#1423](https://github.com/jupyter-naas/abi/issues/1423)).
Each one runs in its own process, registers itself through discovery, and
reaches the engine only over NATS with `naas-abi-sdk`. None imports
`naas_abi_core`, `naas_abi` or `naas_abi_marketplace`.

| Application | Package | Module id | Agent | Replaces |
|---|---|---|---|---|
| Pennylane | `naas_abi_apps.pennylane` | `applications.pennylane` | `Pennylane` | `naas_abi_marketplace.applications.pennylane` |

## Run one

```bash
uv sync --extra pennylane
ABI_NATS_URL=nats://module:<NATS_MODULE_PASSWORD>@127.0.0.1:4222 \
ABI_MODULE_KEY=$(abi module key applications.pennylane) \
ABI_DISCOVERY_PROJECT=<project> \
uv run python -m naas_abi_apps.pennylane
```

It is up when it logs `READY`; its agent then appears in Nexus. Credentials are
engine secrets (e.g. `PENNYLANE_API_KEY`), read through the `secret` service.
Other settings come from `<APP>_<FIELD>` variables (`PENNYLANE_CHAT_MODEL`,
`PENNYLANE_DATASTORE_PATH`, ...).

In a project, add it to `dev.modules` (for `abi dev up`):

```yaml
dev:
  modules:
    - name: pennylane
      module: naas_abi_apps.pennylane
      identity: applications.pennylane
```

and, for Docker, a service built from this folder:

```yaml
services:
  pennylane:
    build:
      context: ./.abi/libs/naas-abi-marketplace-modules
      additional_contexts:
        abi_proto: ./.abi/libs/naas-abi-proto
        abi_sdk: ./.abi/libs/naas-abi-sdk
      args: { APP: pennylane }
    restart: unless-stopped
    environment:
      - ABI_NATS_URL=nats://module:${NATS_MODULE_PASSWORD}@nats:4222
      - ABI_MODULE_KEY=${ABI_MODULE_KEY_PENNYLANE:?abi module key applications.pennylane}
      - ABI_DISCOVERY_PROJECT=<project>
    depends_on: { abi: { condition: service_healthy } }
    networks: [abi-network]
```

Then remove `naas_abi_marketplace.applications.pennylane` from `modules:`.

## Develop

```bash
uv sync --all-extras
uv run pytest            # offline: no broker, no engine, third-party APIs mocked
uvx ruff check naas_abi_apps
```

See `AGENTS.md` for the conventions and the decisions behind this layout.

# {{module_name}}

A remote [ABI](https://github.com/jupyter-naas/abi) module. It runs in its own
process and reaches an ABI engine only through NATS, with `naas-abi-sdk`: an
agent on the engine's models (memory in its Document Service), and an hourly
job. The engine's project must run on NATS with discovery on (projects
created with `abi new project` do).

## Develop

```bash
uv sync
uv run pytest
```

`naas-abi-proto` and `naas-abi-sdk` come from the ABI repository at
`{{abi_git_ref}}` (see `pyproject.toml`).

## Run it against a project

The module needs the broker password of the user `module`, from the
project's `.env`, and its module key: the project derives it from its secret
for the module id, and `abi module key {{module_id}}` (run in the project)
prints it. The module never gets the secret itself, and its key signs tokens
for `{{module_id}}` only.

```bash
export ABI_NATS_URL="nats://module:<NATS_MODULE_PASSWORD>@127.0.0.1:4222"
export ABI_MODULE_KEY="<abi module key {{module_id}}>"
export ABI_DISCOVERY_PROJECT="<the project's nats.discovery.project>"
uv run python -m {{module_name_snake}}
```

It is up when it logs `READY`. Its agent then appears in Nexus. Stop it with
Ctrl+C or SIGTERM: it finishes running work and unregisters.

| Variable | Default | What |
|---|---|---|
| `ABI_NATS_URL` | `nats://127.0.0.1:4222` | the broker, logged in as `module` |
| `ABI_DISCOVERY_PROJECT` | `{{discovery_project}}` | the engine's discovery project |
| `ABI_MODULE_KEY` | | the module key: tokens for `{{module_id}}` are signed with it |
| `ABI_SERVICE_TOKEN` | | an issued service token, used instead of the key |
| `{{module_name_upper}}_CHAT_MODEL` | the engine's default | chat model id |
| `ABI_HEALTH_PORT` | off | `/health` and `/ready` probes |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | off | trace export |

## Container

```bash
docker build -t {{module_name}} .
docker run --rm --network <project>_abi-network \
  -e ABI_NATS_URL="nats://module:<NATS_MODULE_PASSWORD>@nats:4222" \
  -e ABI_MODULE_KEY="<abi module key {{module_id}}>" \
  -e ABI_DISCOVERY_PROJECT="<project>" \
  {{module_name}}
```

The build fails if `naas_abi_core` is installed: the image holds the SDK only.

## Publish

```bash
git init && git add . && git commit -m "Initial commit"
```

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
`{{abi_git_ref}}` (see `pyproject.toml`); they are not on PyPI yet.

## Run it against a project

The module needs its own service key, never a signing secret. In the project,
create its account and key (shown once), then approve its permission manifest
once it has submitted it:

```bash
uv run abi iam service-account create module/<project>/{{module_id}} --key
```

```bash
export ABI_NATS_URL="nats://127.0.0.1:4222"
export ABI_SERVICE_KEY="abi_sk_..."
export ABI_DISCOVERY_PROJECT="<the project's nats.discovery.project>"
uv run python -m {{module_name_snake}}
# waits for approval, logged; in the project:
uv run abi iam module approve module/<project>/{{module_id}}
```

It is up when it logs `READY`. Its agent then appears in Nexus. Stop it with
Ctrl+C or SIGTERM: it finishes running work and unregisters.

| Variable | Default | What |
|---|---|---|
| `ABI_NATS_URL` | `nats://127.0.0.1:4222` | the broker (no login: the key logs in) |
| `ABI_SERVICE_KEY` | required | the module's service key, `abi_sk_...` |
| `ABI_DISCOVERY_PROJECT` | `{{discovery_project}}` | the engine's discovery project |
| `{{module_name_upper}}_CHAT_MODEL` | the engine's default | chat model id |
| `ABI_HEALTH_PORT` | off | `/health` and `/ready` probes |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | off | trace export |

## Container

```bash
docker build -t {{module_name}} .
docker run --rm --network <project>_abi-network \
  -e ABI_NATS_URL="nats://nats:4222" \
  -e ABI_SERVICE_KEY="abi_sk_..." \
  -e ABI_DISCOVERY_PROJECT="<project>" \
  {{module_name}}
```

The build fails if `naas_abi_core` is installed: the image holds the SDK only.

## Publish

```bash
git init && git add . && git commit -m "Initial commit"
```

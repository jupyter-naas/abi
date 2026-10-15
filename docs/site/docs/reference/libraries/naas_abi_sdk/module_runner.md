# module_runner

## What it is
A small CLI entrypoint that imports a Python package exposing `ABIModule` (a `naas_abi_sdk` module), builds its configuration from JSON, fetches a service token from environment variables, and runs the module in an SDK-only asyncio process.

## Public API
- `main() -> None`
  - Parses CLI arguments, loads `ABIModule` from the target package, validates it extends `BaseModule`, builds configuration, and calls `run_module(...)`.

## Configuration/Dependencies
- **Requires** a Python package/module (passed as the positional `module` argument) that exports:
  - `ABIModule` class
  - `ABIModule` must be a subclass of `naas_abi_sdk.module.BaseModule`
  - `ABIModule.Configuration` constructor accepts the JSON fields provided by `--config`
- **Environment variables**
  - `ABI_NATS_URL` (optional): default NATS URL if `--url` not provided (defaults to `nats://127.0.0.1:4222`)
  - Service token variables consumed by `naas_abi_sdk.service_token.token_from_env(os.environ, identity)` (exact names/format defined by that function)
- **Imports/uses**
  - `naas_abi_sdk.module.run_module`
  - `naas_abi_sdk.discovery.DiscoveryConfiguration` (only when `--discovery-project` is set)

## Usage
Run a module by its import path (package name), optionally supplying configuration JSON:

```bash
python -m naas_abi_sdk.module_runner your_package_name \
  --config /path/to/config.json \
  --url nats://127.0.0.1:4222 \
  --timeout 10 \
  --discovery-project your-project
```

Minimal `config.json` example (fields must match `ABIModule.Configuration`):

```json
{}
```

## Caveats
- The target package **must** export `ABIModule`, and it **must** subclass `BaseModule`; otherwise the runner exits with an argparse error.
- `--config` must be valid JSON; invalid JSON will raise an exception during parsing.
- Token acquisition failures from `token_from_env(...)` are surfaced as CLI errors (runner terminates).
- Module identity for token lookup is `ABIModule.module_id` if set, otherwise `ABIModule.__module__`.

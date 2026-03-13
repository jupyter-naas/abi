# `secrets` CLI (naas_abi_cli.cli.secret)

## What it is
A `click`-based command group that manages secrets in Naas, including pushing an `.env` file as a base64-encoded secret and retrieving it back as environment-style key/value output.

## Public API
- `secrets` (Click group: `secrets`)
  - Root command group.
- `naas` (Click subgroup: `secrets naas`)
  - Naas-specific secret commands.

Commands under `secrets naas`:
- `push-env-as-base64`
  - Reads an env file, prints its raw contents, base64-encodes it, and stores it as a Naas secret.
  - Options:
    - `--naas-api-key` (required; default: `NAAS_API_KEY` env var)
    - `--naas-api-url` (required; default: `https://api.naas.ai`)
    - `--naas-secret-name` (required; default: `abi_secrets`)
    - `--env-file` (required; default: `.env.prod`)
- `list`
  - Lists secrets from Naas and prints `key: value` lines.
  - Options:
    - `--naas-api-key` (required; default: `NAAS_API_KEY` env var)
    - `--naas-api-url` (required; default: `https://api.naas.ai`)
- `get-base64-env`
  - Fetches a Naas secret presumed to contain base64-encoded env content and prints it as `KEY=VALUE` lines.
  - If a value contains newlines, it is printed as `KEY="multiline\nvalue"`.
  - Options:
    - `--naas-api-key` (required; default: `NAAS_API_KEY` env var)
    - `--naas-api-url` (required; default: `https://api.naas.ai`)
    - `--naas-secret-name` (required; default: `abi_secrets`)

## Configuration/Dependencies
- Environment:
  - `NAAS_API_KEY` can be used as the default for `--naas-api-key`.
- Python dependencies:
  - `click`
  - `naas_abi_core.services.secret.adaptors.secondary.NaasSecret`
  - `naas_abi_core.services.secret.adaptors.secondary.Base64Secret`
- Network:
  - Calls Naas API at `--naas-api-url` (default `https://api.naas.ai`).

## Usage
Minimal usage via CLI invocation (assuming your package exposes the `secrets` group via an entrypoint):

```bash
export NAAS_API_KEY="your_key"

# Push .env.prod content as base64 into secret "abi_secrets"
naas-abi secrets naas push-env-as-base64 --env-file .env.prod

# List secrets
naas-abi secrets naas list

# Print decoded env-style key/values from the base64 secret
naas-abi secrets naas get-base64-env --naas-secret-name abi_secrets
```

## Caveats
- `push-env-as-base64` prints the raw env file contents to stdout before encoding and pushing; this can leak sensitive values in logs/terminal history.
- `push-env-as-base64` reads the env file directly from disk; missing/unreadable files will raise an exception.
- `list` calls `naas_secret.list()` twice (once unused), potentially resulting in duplicate API calls.

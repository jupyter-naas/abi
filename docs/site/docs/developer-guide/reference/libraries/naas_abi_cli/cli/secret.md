# `secret` (CLI: `secrets naas`)

## What it is
A `click`-based CLI module that manages Naas secrets, including:
- Pushing a local env file as a base64-encoded secret.
- Listing secrets stored in Naas.
- Fetching a base64-encoded env secret and printing it as `KEY=VALUE` lines.

## Public API
- `secrets()`  
  - Click command group: `secrets`.

- `naas()`  
  - Click subgroup: `secrets naas`.

- `push_env_to_naas(naas_api_key, naas_api_url, naas_secret_name, env_file)`  
  - Command: `secrets naas push-env-as-base64`  
  - Reads `env_file`, base64-encodes its full contents, and stores it in Naas under `naas_secret_name`.

- `list_secrets(naas_api_key, naas_api_url)`  
  - Command: `secrets naas list`  
  - Calls `NaasSecret.list()` and prints each `key: value` pair.

- `get_secret(naas_api_key, naas_api_url, naas_secret_name)`  
  - Command: `secrets naas get-base64-env`  
  - Wraps a Naas secret with `Base64Secret`, lists decoded entries, and prints them as env-style lines.

## Configuration/Dependencies
- Environment variables:
  - `NAAS_API_KEY` (used as default for `--naas-api-key`)

- External dependencies:
  - `click`
  - `naas_abi_core.services.secret.adaptors.secondary.NaasSecret.NaasSecret`
  - `naas_abi_core.services.secret.adaptors.secondary.Base64Secret.Base64Secret`
  - Standard library: `os`, `base64`

- CLI options (per-command):
  - `--naas-api-key` (required; default: `os.getenv("NAAS_API_KEY")`)
  - `--naas-api-url` (required; default: `https://api.naas.ai`)
  - `--naas-secret-name` (where applicable; default: `abi_secrets`)
  - `--env-file` (push command only; default: `.env.prod`)

## Usage
Minimal example using Click’s `CliRunner` to invoke the `list` command programmatically:

```python
from click.testing import CliRunner
from naas_abi_cli.cli.secret import secrets

runner = CliRunner()
result = runner.invoke(secrets, ["naas", "list", "--naas-api-key", "YOUR_KEY"])
print(result.output)
```

Typical shell usage (command names as defined by Click):

```bash
# Push .env.prod content as a base64 secret named abi_secrets
secrets naas push-env-as-base64 --naas-api-key "$NAAS_API_KEY"

# List secrets
secrets naas list --naas-api-key "$NAAS_API_KEY"

# Print decoded env entries from base64 secret
secrets naas get-base64-env --naas-api-key "$NAAS_API_KEY"
```

## Caveats
- `push-env-as-base64` prints the full env file contents to stdout before pushing.
- `get-base64-env` wraps multiline values in double quotes when printing (`KEY="multi\nline"`); single-line values are printed as `KEY=value`.

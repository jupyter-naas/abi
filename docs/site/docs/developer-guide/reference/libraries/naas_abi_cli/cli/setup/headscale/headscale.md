# headscale (CLI setup command)

## What it is
A `naas-abi-cli` setup subcommand that triggers local deployment setup with Headscale enabled for the current working directory.

## Public API
- `install()`
  - Registered as a CLI command: `setup headscale`
  - Calls local deploy setup for the current directory with `include_headscale=True`.

## Configuration/Dependencies
- Depends on a CLI command group/object `setup` imported from `..setup`.
- Uses:
  - Standard library: `os.getcwd()`
  - Internal function: `naas_abi_cli.cli.deploy.local.setup_local_deploy`

## Usage
Minimal Python invocation (bypassing CLI registration):

```python
from naas_abi_cli.cli.setup.headscale.headscale import install

install()
```

Typical CLI usage (module command registration implied by the decorator):

```bash
naas-abi-cli setup headscale
```

## Caveats
- Operates on the current working directory (`os.getcwd()`); run it from the target project directory.
- Actual behavior is delegated to `setup_local_deploy(...)`; any requirements or side effects come from that implementation.

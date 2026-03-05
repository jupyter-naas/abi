# headscale

## What it is
A CLI subcommand registration that wires a `headscale` setup command into the parent `setup` CLI group. When invoked, it triggers local deployment setup with Headscale enabled.

## Public API
- `install()`
  - CLI command handler registered as `setup headscale`.
  - Calls local deploy setup for the current working directory with `include_headscale=True`.

## Configuration/Dependencies
- Depends on a parent CLI group/object: `setup` (imported from `..setup`).
- Imports and calls: `setup_local_deploy` from `...deploy.local`.
- Uses `os.getcwd()` to target the current directory.

## Usage
Minimal Python invocation (bypassing the CLI wrapper):

```python
from naas_abi_cli.cli.setup.headscale.headscale import install

install()
```

## Caveats
- Operates on the process current working directory (`os.getcwd()`), so run from the intended project directory.

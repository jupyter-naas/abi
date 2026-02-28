# Managing Dependencies

ABI uses [uv](https://docs.astral.sh/uv/) for Python dependency management across all packages in the monorepo.

## Project Structure

The repo contains four packages, each with its own `pyproject.toml`:

```
abi/
├── pyproject.toml                     # Root workspace config
├── libs/
│   ├── naas-abi-core/pyproject.toml   # Core framework (pipeline, agent, triple store)
│   ├── naas-abi/pyproject.toml        # Main ABI package (agents, ontologies, Nexus)
│   ├── naas-abi-cli/pyproject.toml    # CLI tooling
│   └── naas-abi-marketplace/pyproject.toml  # Community modules
```

All packages are managed from the repo root via `uv` workspace commands.

## Installing Dependencies

```bash
# Install all packages and their dependencies
uv sync --all-extras
```

Run this after cloning, after pulling changes, or after any `pyproject.toml` modification.

## Adding Dependencies

### Add to root project

```bash
make add dep=<package-name>
# e.g.
make add dep=requests
make add dep="requests==2.28.1"
make add dep="uvicorn[standard]"
```

### Add to the core abi library

```bash
make abi-add dep=<package-name>
# e.g.
make abi-add dep=numpy
```

Both commands update the relevant `pyproject.toml` and the `uv.lock` file automatically.

## Updating the Lock File

After manually editing a `pyproject.toml`:

```bash
make lock
```

## Running Commands with Dependencies

uv handles the virtual environment automatically. Prefix any command with `uv run`:

```bash
uv run python your_script.py
uv run abi stack start
uv run pytest
```

## Development Dependencies

Development-only dependencies go in the `[dependency-groups] dev =` section of the relevant `pyproject.toml`. They are installed automatically with `uv sync --all-extras`.

## Resolving Dependency Conflicts

1. Check the error message for the conflicting constraint
2. Edit the relevant `pyproject.toml` to adjust version pins
3. Run `make lock` to re-solve the dependency graph
4. Run `uv sync --all-extras` to install

## Best Practices

- Always use `make add` / `make abi-add` rather than editing `pyproject.toml` directly for new dependencies
- Keep `uv.lock` committed to version control
- After pulling changes from teammates, run `uv sync --all-extras` to stay in sync
- Pin versions for packages where stability matters; leave open ranges for internal libs

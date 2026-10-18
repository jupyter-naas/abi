---
sidebar_position: 2
---

# Managing Dependencies

ABI is a Python monorepo managed with [uv](https://docs.astral.sh/uv/). This page is about working in the ABI repository. A project made with `abi new project` has its own `pyproject.toml`; there, use `uv add` directly (see [Create a module](/user-guide/build/modules/creating-a-module)).

## Project structure

| Project | Path | What it is |
|---|---|---|
| Root (`abi`) | `pyproject.toml`, `uv.lock` | Depends on the packages below and on the marketplace modules the repository runs. |
| `naas-abi-core` | `libs/naas-abi-core` | Engine, service ports and adapters. |
| `naas-abi` | `libs/naas-abi` | Built-in agents, the Nexus app, base ontologies. |
| `naas-abi-cli` | `libs/naas-abi-cli` | The `abi` command. |
| `naas-abi-marketplace` | `libs/naas-abi-marketplace` | Optional modules, each with its own extra. |
| `naas-abi-proto`, `naas-abi-sdk` | `libs/naas-abi-proto`, `libs/naas-abi-sdk` | Protobuf contracts and the SDK for [remote modules](/developer-guide/architecture/remote-modules). They do not depend on `naas-abi-core`. |

Each package has its own `pyproject.toml` and `uv.lock`. The root `pyproject.toml` points at the local copies with editable `[tool.uv.sources]` entries (`naas-abi = { path = "libs/naas-abi", editable = true }`, and so on), so a change in `libs/` shows up in the root environment at once.

Python is pinned to 3.11 in `.python-version`; every package requires `>=3.11,<4`.

## Install

```bash
make deps          # uv sync --all-extras, then pnpm install for the Nexus web app
uv sync --all-extras
```

`uv sync --all-extras` installs every extra of the root project, including the legacy `dagster` and `rabbitmq` extras of `naas-abi-core`: the root `pyproject.toml` asks for `naas-abi-core[all,dagster,rabbitmq]` because the repository still tests them. They are not part of `naas-abi-core[all]`, and a project on NATS does not need them.

The Nexus web app is a Node project: `pnpm install` in `libs/naas-abi/naas_abi/apps/nexus/apps/web` (`make deps` does it when `pnpm` is installed).

`make install` does not work: it depends on a target that does not exist. Use `uv sync --all-extras`.

## Add a dependency

Add it to the package that owns the code that imports it:

```bash
make add dep=requests               # root project
make add-core dep="uvicorn[standard]"
make add-abi dep=numpy
make add-cli dep=rich
make add-marketplace dep="requests==2.32.3"
```

`make add` runs `uv add $(dep)` at the root. The others run `cd libs/<package> && uv add $(dep)`. Each one updates that project's `pyproject.toml` and `uv.lock`. Quote `dep` when it has extras or a version specifier.

A dependency for one marketplace module belongs in that module's extra (`[project.optional-dependencies]` of `libs/naas-abi-marketplace/pyproject.toml`), and the root `pyproject.toml` lists the extras the repository enables (`naas-abi-marketplace[ai-claude]`, ...).

## Update the lock files

```bash
make lock             # uv lock at the root
make deps-upgrade     # uv sync --all-extras --upgrade
cd libs/naas-abi-core && uv lock
```

Commit the `uv.lock` that changed.

## Development dependencies

Test and lint tools (`pytest`, `mypy`, `ruff`, ...) live in `[dependency-groups]` of each `pyproject.toml`, under `dev`. `uv sync` installs the `dev` group by default. Edit the file by hand, then run `uv lock`.

## Work with the environment

```bash
uv run pytest libs/naas-abi-core         # run a tool in the root environment
uv run abi dev up -d                     # run the CLI
uv run python path/to/script.py
```

See [Run Python scripts](./run_python_scripts) and [Test Python scripts](./test_python_scripts). `make check-core` and `make check-marketplace` run `uv sync --all-extras` inside `libs/naas-abi-core`, `libs/naas-abi-cli` and `libs/naas-abi-marketplace` and use that package's own environment (`libs/<package>/.venv`) for `mypy`.

To start again from a clean environment:

```bash
make clean      # removes .venv, caches and the Docker containers (see the Makefile page)
make deps
```

## Resolve a conflict

1. Read the error: uv names the packages and the constraints that clash.
2. Loosen or tighten the version range in the `pyproject.toml` of the package that declares it.
3. Run `uv lock` in that project, then `uv sync --all-extras` at the root.

## Best practices

1. Keep every `uv.lock` under version control.
2. Put a dependency in the package that uses it, not at the root.
3. Keep optional integrations behind an extra, so a deployment installs only what it enables.
4. Upgrade `naas-abi-core`, `naas-abi` and `naas-abi-cli` together: they import each other's modules.
5. After a pull, run `uv sync --all-extras` so your environment matches the lock files.

See also [The Makefile](./makefile).

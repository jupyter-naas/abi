# AGENTS.md
Guidance for coding agents in `/Users/maximejublou/dev/naas/abis/abi`.

## Repo Overview
- Python monorepo managed with `uv`.
- Main packages: `libs/naas-abi-core`, `libs/naas-abi`, `libs/naas-abi-cli`, `libs/naas-abi-marketplace`.
- Root project links local packages via editable `tool.uv.sources` in `pyproject.toml`.
- Python target is `>=3.10,<4`.

## Extra Rules Discovery
- Checked `.cursorrules`: not present.
- Checked `.cursor/rules/`: not present.
- Checked `.github/copilot-instructions.md`: not present.
- Additional instructions are defined in `~/.claude/CLAUDE.md`:
  - Use `gh` CLI for GitHub operations.
  - Follow Hexagonal Architecture.
  - Keep business logic technology-agnostic.
  - Organize as self-sufficient domains with ports/adapters/factories.
  - Prefer TDD (tests first).

## Setup Commands
Run from repository root unless noted.
```bash
uv --version
uv sync --all-extras
```
Alternative bootstrap:
```bash
make deps
```

## Build Commands
```bash
# Python package build (hatchling)
uv build

# Build root Docker image
make build

# Build specific package project
uv build --project libs/naas-abi-core
```

## Lint, Format, Type Check
```bash
# Main quality gates
make check
make check-core
make check-marketplace

# Formatting
make fmt
# or
uvx ruff format

# Lint only
uvx ruff check libs/naas-abi-core libs/naas-abi libs/naas-abi-cli
uvx ruff check libs/naas-abi-marketplace
```

Direct mypy examples:
```bash
cd libs/naas-abi-core && uv sync --all-extras && .venv/bin/mypy -p naas_abi_core --follow-untyped-imports
cd libs/naas-abi-cli && uv sync --all-extras && .venv/bin/mypy -p naas_abi_cli --follow-untyped-imports
```

## Test Commands
```bash
# Full test run
make test
# equivalent
uv run python -m pytest .

# Package-scoped runs
uv run pytest libs/naas-abi-core
uv run pytest libs/naas-abi
uv run pytest libs/naas-abi-cli
uv run pytest libs/naas-abi-marketplace
```

Single-test execution (important):
```bash
# single file
uv run pytest libs/naas-abi-core/naas_abi_core/apps/api/api_test.py -v

# single class
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/adapters/secondary/PythonAdapter_test.py::TestPythonAdapter -v

# single test function
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/adapters/secondary/PythonAdapter_test.py::TestPythonAdapter::test_set_get_exists_delete -v

# keyword filtering
uv run pytest libs/naas-abi-core -k "postgres or checkpointer" -v
```

Notes:
- `pytest.ini` enables strict markers/config and coverage output.
- Test naming in this repo uses both `*_test.py` and `test_*.py`; follow nearby files.

## Architecture Guidelines
- Keep strict Ports-and-Adapters boundaries.
- Domain logic must not depend on concrete infrastructure details.
- Preserve self-contained domain structure: interfaces, domain, primary adapters, secondary adapters, factories, tests.
- Reuse/add generic adapter tests for new adapters when relevant.
- Do not bypass architecture with direct infra calls from domain code.

## Code Style Guidelines
### Imports
- Prefer absolute imports from package roots (`naas_abi_core...`, `naas_abi...`).
- Group imports: standard library, third-party, local package.
- Keep imports explicit and remove unused ones.

### Formatting
- Use `ruff format` as canonical formatter.
- Preserve local style in touched files.
- Keep diffs clean (trailing commas in multiline blocks where appropriate).

### Typing
- Add type hints to new/changed public APIs.
- Prefer modern built-in generics (`list[str]`, `dict[str, Any]`).
- Keep port interfaces strongly typed; adapters must conform to port signatures.

### Naming
- Match naming conventions of the directory you modify.
- In `naas_abi_core`, many production files use `PascalCase.py`; keep that style in-place.
- Test functions use `test_...`; test classes use `Test...`.

### Error Handling
- Raise specific exceptions at domain/service boundaries.
- Catch exceptions at adapter or API boundaries for translation/fallback.
- Log actionable errors with repository logger utilities.
- Do not silently swallow exceptions.

### Testing Discipline
- Prefer TDD for new behaviors.
- Update colocated tests whenever behavior changes.
- Keep tests deterministic; isolate integration requirements explicitly.

## Agent Operating Rules
- Use `gh` CLI for PRs/issues/comments/checks/releases.
- Keep changes scoped; avoid broad refactors unless requested.
- Preserve existing architecture patterns over stylistic rewrites.
- If unsure, follow nearest module conventions.

## Quick Cheat Sheet
```bash
make deps
make check
make fmt
make test
uv build
```

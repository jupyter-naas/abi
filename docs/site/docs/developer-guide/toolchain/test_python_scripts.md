---
sidebar_position: 8
---

# Test Python Scripts

Tests keep ABI maintainable. ABI uses [pytest](https://docs.pytest.org/). This page covers how to name and place tests, how to write them, and how to run them, in the ABI repository and in a project made with `abi new project`.

## Naming and placement

Test files end in `_test.py` and sit next to the code they test. Some older files use `test_*.py`; follow the neighbours. Where a test goes depends on what it covers:

- **Beside its source**, for a test of one file: `users.py` has `users_test.py`. It is found where the code is and moves with it.
- **In the module's `tests/` folder**, for a test with no single natural neighbour: behaviour of the whole module, or something defined in its `__init__.py`. `tests/` also holds shared fixtures, such as an `artifacts/` folder.

Both forms are intentional. Do not consolidate them.

```text
libs/naas-abi-core/naas_abi_core/services/keyvalue/
├── KeyValuePorts.py
├── adapters/secondary/
│   ├── PythonAdapter.py
│   └── PythonAdapter_test.py                     # one file, one neighbour
└── tests/
    └── kv__secondary_adapter__generic_test.py    # the contract every adapter must pass
```

In a generated project, modules live under `src/<module>/`. A remote module made by `abi new module` comes with `tests/module_test.py`; for the other files you add the tests yourself, beside the code:

```text
src/my_module/
├── __init__.py
├── agents/
│   ├── MyAgent.py
│   └── MyAgent_test.py
└── tests/
    └── module_test.py
```

## Writing tests

Tests are plain pytest: functions named `test_...`, classes named `Test...`, and fixtures for setup.

```python
import pytest

from my_module.calculator import Calculator


@pytest.fixture
def calculator() -> Calculator:
    return Calculator()


def test_addition(calculator: Calculator) -> None:
    assert calculator.add(2, 3) == 5


def test_division_by_zero(calculator: Calculator) -> None:
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        calculator.divide(5, 0)


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(2, 3, 5), (0, 0, 0), (-1, 1, 0)],
)
def test_addition_parametrized(calculator: Calculator, a: int, b: int, expected: int) -> None:
    assert calculator.add(a, b) == expected
```

### Keep tests offline and deterministic

- A test should not need a running stack. Unit tests build the object under test directly and use the in-memory or file adapters (`PythonAdapter`, SQLite, `tmp_path`), not Postgres, Fuseki or a NATS broker.
- Tests that need an external service are marked `@pytest.mark.integration` (the marker is declared in `libs/naas-abi-core/pyproject.toml`) and read their connection from the environment, for example `DOCUMENT_TEST_POSTGRES_DSN` for PostgreSQL. Without it, the PostgreSQL cases do not run.
- A remote module's tests run with no broker and no engine: the module scaffolded by `abi new module` checks its declared agents, services and jobs, its configuration from the environment, and that it never imports `naas_abi_core`. Keep that property.
- Do not call a model provider in a test.

### Adapters: run the generic contract

Every service has a generic contract test in its `tests/` folder. A new adapter subclasses it and supplies the `adapter` fixture, so it gets the whole suite:

```python
class TestPythonAdapter(GenericKVSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return PythonAdapter

    @pytest.fixture
    def adapter(self):
        return PythonAdapter()
```

Each service's `AGENTS.md` (under `libs/naas-abi-core/naas_abi_core/services/<service>/`) names the contract test and how to run it.

### Async code

Remote-module code is async (`naas-abi-sdk`). The SDK's tests and the module scaffolded by `abi new module` drive a coroutine from a plain test function with `asyncio.run`:

```python
import asyncio


def test_the_call_returns() -> None:
    async def scenario() -> None:
        assert await my_coroutine() == "ok"

    asyncio.run(scenario())
```

## Running tests

From the repository root:

```bash
uv run pytest libs/naas-abi-core                   # one package
uv run pytest libs/naas-abi libs/naas-abi-cli      # several
make test                                          # uv run python -m pytest .  (everything)
```

One file, one class, one test, a keyword:

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/apps/api/api_test.py -v
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/adapters/secondary/PythonAdapter_test.py::TestPythonAdapter -v
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/adapters/secondary/PythonAdapter_test.py::TestPythonAdapter::test_set_get_exists_delete -v
uv run pytest libs/naas-abi-core -k "postgres or checkpointer" -v
```

Options you will use most:

| Option | Meaning |
|---|---|
| `-v` | Verbose output. |
| `-s` | Show `print` output. |
| `-k "pattern"` | Run the tests whose name matches. |
| `-m integration` / `-m "not integration"` | Select or skip the marked tests. |
| `-x` | Stop at the first failure. |
| `--tb=short` | Shorter tracebacks. |
| `-n auto` | Run in parallel (`pytest-xdist` is in the dev group). |
| `--cov=<package>` | Coverage report (`pytest-cov` is in the dev group). |

### Targets with their own setup

The Makefile has targets for suites that need a flag, a Docker container or a database; see [The Makefile](./makefile#tests):

```bash
make test-api                   # the API tests
make test-local-embedded-core   # the no-Docker embedded engine end to end
make test-integration-core      # triple store integration tests (testcontainers, needs Docker)
make test-document-core         # document service; set DOCUMENT_TEST_POSTGRES_DSN for PostgreSQL
make test-event-core            # event and activity log
make test-agent-memory-core     # agent memory jobs and checkpoint migration
make test-sdk                   # naas-abi-proto and naas-abi-sdk
```

Tests that build an `Engine()` from the repository's root config run on NATS like everything else there, so they need a broker at `127.0.0.1:4222` (the Docker stack's, `abi stack start`). To load the engine in-process instead, point `ABI_CONFIG_OVERLAY` at a YAML file that holds `nats: null`. Details: [The Makefile](./makefile#which-targets-need-nats).

### The CLI end to end

`scripts/cli_smoke.sh` runs the `abi` CLI the way a user does: it creates a project in a temporary folder, adds modules, starts it with `abi dev up -d`, checks the API, the agents and Nexus, then stops it. It needs `uv`, `git`, `curl`, `python3`, `pnpm` and `nats-server` 2.14 or later, but no Docker and no model. CI runs it on every pull request into `main`.

```bash
scripts/cli_smoke.sh            # both variants, 5 to 10 minutes each
scripts/cli_smoke.sh nats       # the default project
scripts/cli_smoke.sh without-nats   # the legacy project, without NATS
```

### In a generated project

```bash
uv run pytest
```

runs the tests under `src/` (`testpaths = ["src"]`, files `*_test.py` and `test_*.py`). `uv sync --no-dev` leaves pytest out. A remote module created with `--standalone` has its own `tests/` folder and its own `pytest` configuration.

## Troubleshooting

**pytest does not find a test.** The file must end in `_test.py` (or start with `test_`), and the function must start with `test_`. Check that the file is under a path pytest collects (`testpaths`).

**Import errors.** Run through `uv run`, so the project's environment is used. Use absolute imports (`naas_abi_core...`, `my_module...`), as the rest of the code does.

**`EngineAlreadyServing`, or connection refused on 4222.** The test builds an engine in NATS mode. Start a broker, stop the other engine, or use the `nats: null` overlay. See [Running Python scripts](./run_python_scripts#a-script-that-builds-its-own-engine).

**A fixture is not found.** The name must match the parameter, and the fixture must be in the same file or in a `conftest.py` above it.

## Best practices

1. Keep tests next to the code they cover; use `tests/` for what spans a module.
2. Name tests after the behaviour (`test_division_by_zero`), and test the failure cases as well as the success.
3. Prefer fixtures and `parametrize` to copy-paste.
4. Update the test in the same change as the behaviour. A new behaviour gets its test first where you can.
5. Keep integration requirements explicit: a marker, an environment variable, a skip.

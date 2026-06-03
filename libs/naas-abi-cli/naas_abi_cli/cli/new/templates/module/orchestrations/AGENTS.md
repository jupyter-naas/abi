# `orchestrations/` — AGENTS.md

> Scope: orchestrations for the `{{module_name_snake}}` module. See the module's [AGENTS.md](../AGENTS.md) for module-wide context.

## What goes here

**Dagster** orchestration units. An orchestration bundles `assets`, `jobs`, `schedules`, and `sensors` into a single `dg.Definitions` and lets the engine run scheduled / triggered work.

Use orchestrations when you need:
- **Recurring runs** (cron-like schedules) of a workflow or pipeline.
- **Event-driven triggers** (Dagster sensors watching upstream state).
- **Asset materialisation** with lineage and partitioning.

For one-shot agent-callable work, use a `workflow` instead.

## File shape

Files are `PascalCase`, one orchestration per file: `<Name>Orchestration.py`.

```python
import dagster as dg
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration

class <Name>Orchestration(DagsterOrchestration):

    @classmethod
    def New(cls) -> "<Name>Orchestration":
        return cls(
            definitions=dg.Definitions(
                assets=[
                    # @dg.asset(...) functions
                ],
                schedules=[
                    # dg.ScheduleDefinition(...)
                ],
                jobs=[
                    # dg.JobDefinition(...)
                ],
                sensors=[
                    # dg.SensorDefinition(...)
                ],
            )
        )
```

## Conventions

- **`.New()` classmethod factory** — never instantiate the orchestration directly.
- **One orchestration per file**; one `dg.Definitions` per orchestration.
- **Assets / jobs / schedules / sensors live as top-level functions** in the same file (or split into a helper module if it grows). Keep them in the same Python module so Dagster discovery is local.
- **Wrap workflows / pipelines** as ops or assets — don't reimplement business logic here.

## Scaffold a new orchestration

```bash
abi new orchestration <name> .
```

This drops `<Name>Orchestration.py` with the empty `Definitions` skeleton.

## Tests

Colocated as `<Name>Orchestration_test.py`. Verify the `Definitions` is well-formed and key jobs / schedules are present:

```python
import dagster as dg
from {{module_name_snake}}.orchestrations.<Name>Orchestration import <Name>Orchestration

def test_definitions_load():
    orch = <Name>Orchestration.New()
    defs = orch.definitions
    assert isinstance(defs, dg.Definitions)
    # assert any specific job/schedule names you expect
```

Run:

```bash
uv run pytest {{module_name_snake}}/orchestrations
uv run pytest {{module_name_snake}}/orchestrations/<Name>Orchestration_test.py -v
```

## Wiring into the module

1. Expose the orchestration via the module's `on_initialized()` hook so the engine's Dagster app picks it up at startup.
2. Reference the workflows / pipelines you want to run from this module's `../workflows/` and `../pipelines/`.
3. If the orchestration needs secrets (e.g. external API tokens), pull them from the module's `Configuration` — not from `os.environ` directly.

## See also

- Dagster app entry point in core: [`.abi/libs/naas-abi-core/.../apps/dagster/`](../../../.abi/libs/naas-abi-core/naas_abi_core/apps/dagster)
- Reference patterns: [`.abi/libs/naas-abi-marketplace/.../__demo__/orchestration/definitions.py`](../../../.abi/libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/orchestration/definitions.py)
- Module-level [AGENTS.md](../AGENTS.md) — lifecycle hooks (`on_load`, `on_initialized`, `api`).

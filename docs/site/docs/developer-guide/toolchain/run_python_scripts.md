---
sidebar_position: 4
---

# Running Python Scripts with uv

There are three ways to run a Python script that uses ABI. They differ in who loads the engine.

## A script with no engine

A script that imports `naas_abi_core` classes but needs no running services runs like any Python file, in the environment uv manages:

```bash
uv run python path/to/script.py
```

In a project made with `abi new project`, run it from the project root, so that its `pyproject.toml` and virtual environment are used.

## `abi run script`: the engine, already loaded

```bash
abi run script path/to/script.py --foo bar
```

The command loads the engine from the project's config (`Engine().load()`), then runs the file with `runpy` as `__main__`. Arguments after the path go to the script's own `sys.argv`, so `argparse` or `click` in the script works as usual. Inside a project, `abi` re-runs itself in the project's virtual environment, so it uses the project's versions.

It runs with the engine role `auto` (unless `ABI_ENGINE_ROLE` is set). In NATS mode, one engine serves the kernel services; a script run this way serves them when no engine does, and is a client of the serving engine otherwise. So it works next to a running `abi dev up` or `abi stack start`, and without them, as long as the NATS broker of the config is reachable. See [One serving engine](/developer-guide/architecture/nats#one-serving-engine).

## A script that builds its own engine

A script can build the engine itself, with the `__main__` pattern. This is how the scripts in the repository's `scripts/` folder work (`scripts/export_triplestore_turtle.py`, for example):

```python
# scripts/list_triples.py
if __name__ == "__main__":
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi"])

    triple_store = engine.services.triple_store
    with triple_store.query_stream("SELECT * WHERE { ?s ?p ?o } LIMIT 10") as result:
        for row in result.rows:
            print(row)
```

Run it with `uv run python scripts/list_triples.py`.

An `Engine()` in NATS mode serves the kernel services by default (`nats.engine.role: serve`). If another engine already serves, the script fails at start with `EngineAlreadyServing`. Choose one:

- Set `ABI_ENGINE_ROLE=client` to use the running engine's services without serving or opening any backend of your own.
- Set `ABI_ENGINE_ROLE=auto` to serve only when nobody does.
- Stop the other engine first.

Without NATS (the legacy in-process engine), there is no lease, and the script opens the backends itself.

`engine.load(module_names=[...])` loads only the modules you name. Without the argument it loads every enabled module of the config.

## Run an application of the repository

The Makefile has shortcuts for the common ones; they all need a NATS broker (see [The Makefile](./makefile#which-targets-need-nats)):

```bash
make api                  # the API in the foreground
make chat-abi-agent       # terminal chat with the main agent
make chat module_name=naas_abi agent_name=AbiAgent
```

The same, with the CLI: `abi chat <module> <agent>`, or `abi dev up -d` to run everything natively. A project made with `abi new project` uses `abi`, not `make`.

## Debugging tips

- Use the `logging` module, or `naas_abi_core.logger`, rather than `print`, so output reaches the logs of the process that runs the code.
- Set `LOG_LEVEL=DEBUG` to see the engine's boot phases. At `DEBUG` the engine also logs model prompts, so keep production at `INFO`.
- `breakpoint()` stops in the debugger of your choice when you run the script in the foreground.
- To see what a service did, read the logs (`abi dev logs api -f`, or `docker compose logs -f abi`) and the [System app](/developer-guide/architecture/observability) of Nexus.

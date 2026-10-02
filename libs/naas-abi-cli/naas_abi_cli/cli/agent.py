import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import click
from naas_abi_core.engine.Engine import Engine
from rich.console import Console
from rich.table import Table


@click.group("agent")
def agent():
    pass


@agent.command("list")
def list():
    engine = Engine()
    engine.load()

    console = Console()
    table = Table(
        title="Available Agents", show_header=True, header_style="bold magenta"
    )
    table.add_column("Module", style="cyan", no_wrap=True)
    table.add_column("Agent", style="green")

    modules = engine.modules

    # Sort modules alphabetically
    sorted_modules = sorted(modules.keys())

    for module in sorted_modules:
        # Sort agents alphabetically by name
        sorted_agents = sorted(modules[module].agents, key=lambda agent: agent.__name__)
        for agent in sorted_agents:
            table.add_row(module, agent.__name__)

    console.print(table)


@contextmanager
def _postgres_memory(url: str) -> Iterator[tuple[Any, Sequence[str]]]:
    """LangGraph's PostgreSQL saver on ``url`` and its thread IDs, read only."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from naas_abi_core.services.agent.CheckpointMigration import postgres_thread_ids
    from psycopg import Connection
    from psycopg.rows import dict_row

    with Connection.connect(
        url, autocommit=True, prepare_threshold=0, row_factory=dict_row
    ) as connection:
        yield PostgresSaver(connection), postgres_thread_ids(connection)


def _documents(namespace: str) -> Any:
    """This project's document service (``config.yaml``), bound to ``namespace``."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )

    root = EngineConfiguration.load_configuration().services.document.load()
    return root.for_namespace(namespace)


@contextmanager
def _source(origin: str, url: str | None, namespace: str, agent_id: str):
    if origin == "documents-v1":
        from naas_abi_core.services.agent.DocumentCheckpointSaver import (
            LegacyDocumentCheckpointReader,
        )

        reader = LegacyDocumentCheckpointReader(
            _documents(namespace), agent_id=agent_id
        )
        yield reader, reader.thread_ids()
        return
    if not url:
        raise click.UsageError("Set POSTGRES_URL or pass --source-url.")
    with _postgres_memory(url) as opened:
        yield opened


@agent.command("migrate-memory")
@click.option(
    "--from",
    "origin",
    type=click.Choice(["postgres", "documents-v1"]),
    default="postgres",
    show_default=True,
    help="LangGraph's PostgreSQL tables, or document schema 1 (full snapshots).",
)
@click.option(
    "--source-url",
    envvar="POSTGRES_URL",
    show_envvar=True,
    help="With --from postgres: LangGraph's PostgreSQL database.",
)
@click.option(
    "--namespace",
    default=None,
    help="Document namespace (default: the engine's agent memory).",
)
@click.option(
    "--agent-id", default=None, help="Checkpoint scope (default: the engine's)."
)
@click.option(
    "--thread", "threads", multiple=True, help="Only this thread ID (repeatable)."
)
@click.option(
    "--apply", is_flag=True, help="Write to the document service; else only report."
)
def migrate_memory(
    origin: str,
    source_url: str | None,
    namespace: str | None,
    agent_id: str | None,
    threads: tuple[str, ...],
    apply: bool,
):
    """Copy agent memory into the document service (schema 2, increments).

    From LangGraph's PostgreSQL tables or from document schema 1, into the same
    namespace and agent id. A dry run unless --apply. Idempotent: run it again
    to copy what is missing. Stop the engines (API, Dagster) first, then start
    them on the new version.
    """
    from naas_abi_core.services.agent.CheckpointMigration import migrate_checkpoints
    from naas_abi_core.services.agent.DocumentCheckpointSaver import (
        ENGINE_MEMORY_ID,
        ENGINE_MEMORY_NAMESPACE,
        DocumentCheckpointSaver,
    )

    namespace = namespace or ENGINE_MEMORY_NAMESPACE
    agent_id = agent_id or ENGINE_MEMORY_ID
    with _source(origin, source_url, namespace, agent_id) as (source, thread_ids):
        target = None
        if apply:
            target = DocumentCheckpointSaver(
                _documents(namespace), agent_id=agent_id, legacy_reads=False
            )
            target.setup()
        summary = migrate_checkpoints(source, target, threads=threads or thread_ids)
    report = {
        "mode": "applied" if apply else "dry-run",
        "source": origin,
        "target": {"namespace": namespace, "agent_id": agent_id, "schema": 2},
        **summary.as_dict(),
    }
    click.echo(json.dumps(report, indent=2))

"""``abi stack snapshot`` -- capture, restore, and move the Docker stack's data.

Snapshots are stored under ``./.snapshots/<id>/`` in the project root. Each one
is a cold, consistent copy of the stateful volumes plus the host ``storage/``
directory, taken while the stack is briefly stopped. See
:mod:`naas_abi_cli.cli.snapshot_runtime` for the underlying logic.
"""

from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table

from . import snapshot_runtime as runtime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


@click.group("snapshot")
def snapshot() -> None:
    """Create, restore, and move snapshots of the Docker stack's data."""


@snapshot.command("create")
@click.option("-m", "--note", default="", help="A note describing this snapshot.")
@click.option(
    "--name",
    "slug",
    default=None,
    help="Optional label appended to the snapshot id.",
)
def snapshot_create(note: str, slug: str | None) -> None:
    """Stop the stack, archive its data, then restart it."""
    manifest = runtime.create_snapshot(note=note, slug=slug, now=_now())
    click.echo(
        f"Created snapshot '{manifest.id}' "
        f"({_human_size(manifest.size_bytes)}, volumes: "
        f"{', '.join(manifest.volumes) or 'none'})."
    )


@snapshot.command("list")
def snapshot_list() -> None:
    """List available snapshots, newest first."""
    manifests = runtime.list_snapshots()
    if not manifests:
        click.echo("No snapshots yet. Create one with 'abi stack snapshot create'.")
        return

    table = Table(title="ABI Stack Snapshots")
    table.add_column("ID")
    table.add_column("Created (UTC)")
    table.add_column("Size")
    table.add_column("Commit")
    table.add_column("Note")
    for manifest in manifests:
        table.add_row(
            manifest.id,
            manifest.created_at,
            _human_size(manifest.size_bytes),
            manifest.git_commit or "-",
            manifest.note or "-",
        )
    Console().print(table)


@snapshot.command("restore")
@click.argument("snapshot_id")
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip the confirmation prompt.",
)
@click.option(
    "--safety-snapshot/--no-safety-snapshot",
    default=True,
    show_default=True,
    help="Take a safety snapshot of the current state before restoring.",
)
def snapshot_restore(snapshot_id: str, yes: bool, safety_snapshot: bool) -> None:
    """Roll the stack back to snapshot SNAPSHOT_ID (destructive)."""
    if not yes:
        click.confirm(
            f"This overwrites the current stack data with snapshot "
            f"'{snapshot_id}'. Continue?",
            abort=True,
        )
    runtime.restore_snapshot(snapshot_id, safety=safety_snapshot, now=_now())
    click.echo(f"Restored snapshot '{snapshot_id}'.")


@snapshot.command("delete")
@click.argument("snapshot_id")
@click.option("--yes", is_flag=True, default=False, help="Skip the confirmation prompt.")
def snapshot_delete(snapshot_id: str, yes: bool) -> None:
    """Delete a snapshot."""
    if not yes:
        click.confirm(f"Delete snapshot '{snapshot_id}'?", abort=True)
    runtime.delete_snapshot(snapshot_id)
    click.echo(f"Deleted snapshot '{snapshot_id}'.")


@snapshot.command("prune")
@click.option(
    "--keep",
    type=int,
    default=5,
    show_default=True,
    help="Number of newest snapshots to keep.",
)
@click.option("--yes", is_flag=True, default=False, help="Skip the confirmation prompt.")
def snapshot_prune(keep: int, yes: bool) -> None:
    """Delete all but the newest --keep snapshots."""
    victims = runtime.select_prunable(runtime.list_snapshots(), keep)
    if not victims:
        click.echo("Nothing to prune.")
        return
    if not yes:
        click.confirm(
            f"Delete {len(victims)} snapshot(s): {', '.join(victims)}?", abort=True
        )
    for snapshot_id in victims:
        runtime.delete_snapshot(snapshot_id)
    click.echo(f"Pruned {len(victims)} snapshot(s).")


@snapshot.command("export")
@click.argument("snapshot_id")
@click.argument("destination", type=click.Path(dir_okay=False))
@click.option("--force", is_flag=True, default=False, help="Overwrite the destination if it exists.")
def snapshot_export(snapshot_id: str, destination: str, force: bool) -> None:
    """Export a snapshot to a single portable archive for another host."""
    from pathlib import Path

    path = runtime.export_snapshot(snapshot_id, Path(destination), force=force)
    click.echo(f"Exported snapshot '{snapshot_id}' to {path}.")


@snapshot.command("import")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False))
@click.option("--force", is_flag=True, default=False, help="Replace an existing snapshot with the same id.")
def snapshot_import(archive: str, force: bool) -> None:
    """Import a snapshot archive produced by 'export' on another host."""
    from pathlib import Path

    snapshot_id = runtime.import_snapshot(Path(archive), force=force)
    click.echo(
        f"Imported snapshot '{snapshot_id}'. "
        f"Restore it with 'abi stack snapshot restore {snapshot_id}'."
    )

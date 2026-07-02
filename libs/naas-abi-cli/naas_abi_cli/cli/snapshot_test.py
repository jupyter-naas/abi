from click.testing import CliRunner

from naas_abi_cli.cli import snapshot_runtime as rt
from naas_abi_cli.cli.snapshot import snapshot as snapshot_group
from naas_abi_cli.cli.snapshot_runtime import SnapshotManifest


def _manifest(snapshot_id: str = "20260630-140509") -> SnapshotManifest:
    return SnapshotManifest(
        id=snapshot_id,
        created_at="2026-06-30T14:05:09+00:00",
        note="pre-migration",
        git_commit="abc1234",
        volumes=["postgres_data", "minio_data"],
        size_bytes=2048,
    )


def test_create_reports_new_snapshot(monkeypatch) -> None:
    captured: dict = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return _manifest()

    monkeypatch.setattr(rt, "create_snapshot", _create)
    result = CliRunner().invoke(snapshot_group, ["create", "-m", "pre-migration"])

    assert result.exit_code == 0
    assert "20260630-140509" in result.output
    assert captured["note"] == "pre-migration"


def test_list_renders_rows(monkeypatch) -> None:
    monkeypatch.setattr(rt, "list_snapshots", lambda: [_manifest()])
    result = CliRunner().invoke(snapshot_group, ["list"])
    assert result.exit_code == 0
    assert "20260630-140509" in result.output


def test_list_handles_empty(monkeypatch) -> None:
    monkeypatch.setattr(rt, "list_snapshots", lambda: [])
    result = CliRunner().invoke(snapshot_group, ["list"])
    assert result.exit_code == 0
    assert "No snapshots yet" in result.output


def test_restore_with_yes_skips_prompt_and_keeps_safety_default(monkeypatch) -> None:
    captured: dict = {}

    def _restore(snapshot_id, **kwargs):
        captured["id"] = snapshot_id
        captured.update(kwargs)
        return _manifest(snapshot_id)

    monkeypatch.setattr(rt, "restore_snapshot", _restore)
    result = CliRunner().invoke(
        snapshot_group, ["restore", "20260630-140509", "--yes"]
    )

    assert result.exit_code == 0
    assert captured["id"] == "20260630-140509"
    assert captured["safety"] is True


def test_restore_prompts_when_not_confirmed(monkeypatch) -> None:
    called = {"count": 0}
    monkeypatch.setattr(
        rt, "restore_snapshot", lambda *a, **k: called.__setitem__("count", 1)
    )
    # Decline the confirmation prompt.
    result = CliRunner().invoke(
        snapshot_group, ["restore", "20260630-140509"], input="n\n"
    )
    assert result.exit_code != 0
    assert called["count"] == 0


def test_restore_no_safety_flag(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        rt, "restore_snapshot", lambda snapshot_id, **k: captured.update(k)
    )
    result = CliRunner().invoke(
        snapshot_group,
        ["restore", "20260630-140509", "--yes", "--no-safety-snapshot"],
    )
    assert result.exit_code == 0
    assert captured["safety"] is False


def test_delete_with_yes(monkeypatch) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(rt, "delete_snapshot", lambda sid: deleted.append(sid))
    result = CliRunner().invoke(
        snapshot_group, ["delete", "20260630-140509", "--yes"]
    )
    assert result.exit_code == 0
    assert deleted == ["20260630-140509"]


def test_prune_deletes_selected(monkeypatch) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(rt, "list_snapshots", lambda: [_manifest("a"), _manifest("b")])
    monkeypatch.setattr(rt, "select_prunable", lambda manifests, keep: ["b"])
    monkeypatch.setattr(rt, "delete_snapshot", lambda sid: deleted.append(sid))
    result = CliRunner().invoke(snapshot_group, ["prune", "--keep", "1", "--yes"])
    assert result.exit_code == 0
    assert deleted == ["b"]


def test_prune_nothing_to_do(monkeypatch) -> None:
    monkeypatch.setattr(rt, "list_snapshots", lambda: [])
    monkeypatch.setattr(rt, "select_prunable", lambda manifests, keep: [])
    result = CliRunner().invoke(snapshot_group, ["prune", "--yes"])
    assert result.exit_code == 0
    assert "Nothing to prune" in result.output


def test_export_reports_destination(monkeypatch, tmp_path) -> None:
    from pathlib import Path

    monkeypatch.setattr(
        rt, "export_snapshot", lambda sid, dest, **k: Path(dest)
    )
    out = tmp_path / "snap.tar.gz"
    result = CliRunner().invoke(
        snapshot_group, ["export", "20260630-140509", str(out)]
    )
    assert result.exit_code == 0
    assert str(out) in result.output


def test_import_reports_snapshot_id(monkeypatch, tmp_path) -> None:
    archive = tmp_path / "snap.tar.gz"
    archive.write_bytes(b"x")
    monkeypatch.setattr(rt, "import_snapshot", lambda src, **k: "20260630-140509")
    result = CliRunner().invoke(
        snapshot_group, ["import", str(archive)]
    )
    assert result.exit_code == 0
    assert "20260630-140509" in result.output

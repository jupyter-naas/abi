import io
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import click
import pytest

from naas_abi_cli.cli import snapshot_runtime as rt
from naas_abi_cli.cli.snapshot_runtime import SnapshotManifest

FIXED_NOW = datetime(2026, 6, 30, 14, 5, 9, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def test_sanitize_slug_normalises_text() -> None:
    assert rt.sanitize_slug("  Before Big Migration!! ") == "before-big-migration"
    assert rt.sanitize_slug("a___b") == "a-b"
    assert rt.sanitize_slug("!!!") == ""


def test_generate_snapshot_id_with_and_without_slug() -> None:
    assert rt.generate_snapshot_id(FIXED_NOW) == "20260630-140509"
    assert rt.generate_snapshot_id(FIXED_NOW, "Pre Upgrade") == "20260630-140509-pre-upgrade"
    # A slug that sanitises to empty is dropped.
    assert rt.generate_snapshot_id(FIXED_NOW, "***") == "20260630-140509"


def test_sanitize_project_name_matches_compose_rules() -> None:
    assert rt.sanitize_project_name("My.Project Name") == "myprojectname"
    assert rt.sanitize_project_name("__abi-core") == "abi-core"


def test_parse_project_name() -> None:
    assert rt.parse_project_name('{"name": "abi"}') == "abi"
    assert rt.parse_project_name('{"name": ""}') is None
    assert rt.parse_project_name("not json") is None
    assert rt.parse_project_name("[1, 2]") is None


def test_volume_full_name() -> None:
    assert rt.volume_full_name("abi", "postgres_data") == "abi_postgres_data"


def test_select_prunable_keeps_newest() -> None:
    manifests = [
        SnapshotManifest(id="a", created_at="2026-01-01T00:00:00"),
        SnapshotManifest(id="b", created_at="2026-03-01T00:00:00"),
        SnapshotManifest(id="c", created_at="2026-02-01T00:00:00"),
    ]
    assert rt.select_prunable(manifests, keep=1) == ["c", "a"]
    assert rt.select_prunable(manifests, keep=0) == ["b", "c", "a"]
    assert rt.select_prunable(manifests, keep=5) == []


def test_select_prunable_rejects_negative_keep() -> None:
    with pytest.raises(ValueError):
        rt.select_prunable([], keep=-1)


def test_detect_drift_reports_commit_and_config_changes() -> None:
    manifest = SnapshotManifest(
        id="x",
        created_at="2026-01-01T00:00:00",
        git_commit="aaaaaaa",
        config_hashes={"config.local.yaml": "h1", ".env": "h2"},
    )
    messages = rt.detect_drift(
        manifest,
        current_commit="bbbbbbb",
        current_hashes={"config.local.yaml": "h1", ".env": "DIFFERENT"},
    )
    assert any("git commit differs" in m for m in messages)
    assert any(".env has changed" in m for m in messages)
    assert not any("config.local.yaml has changed" in m for m in messages)


def test_detect_drift_silent_when_unchanged() -> None:
    manifest = SnapshotManifest(
        id="x",
        created_at="2026-01-01T00:00:00",
        git_commit="aaaaaaa",
        config_hashes={"config.local.yaml": "h1"},
    )
    assert rt.detect_drift(manifest, "aaaaaaa", {"config.local.yaml": "h1"}) == []


def test_manifest_json_round_trip() -> None:
    manifest = SnapshotManifest(
        id="20260630-140509",
        created_at=FIXED_NOW.isoformat(),
        note="hello",
        project="abi",
        volumes=["postgres_data", "minio_data"],
        storage_included=True,
        config_hashes={".env": "abc"},
        size_bytes=1234,
    )
    restored = SnapshotManifest.from_json(manifest.to_json())
    assert restored == manifest


def test_manifest_from_json_ignores_unknown_fields() -> None:
    restored = SnapshotManifest.from_json(
        '{"id": "x", "created_at": "t", "surprise_field": 1}'
    )
    assert restored.id == "x"
    assert restored.created_at == "t"


# --------------------------------------------------------------------------- #
# Filesystem helpers
# --------------------------------------------------------------------------- #
def test_config_hashes_only_includes_present_files(tmp_path: Path) -> None:
    (tmp_path / "config.local.yaml").write_text("a: 1", encoding="utf-8")
    hashes = rt.config_hashes(tmp_path)
    assert "config.local.yaml" in hashes
    assert ".env" not in hashes


def test_archive_and_extract_storage_round_trip(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    (source_root / "storage" / "events").mkdir(parents=True)
    (source_root / "storage" / "events" / "events.sqlite").write_text(
        "data", encoding="utf-8"
    )
    archive = tmp_path / "storage.tar.gz"
    rt.archive_storage(source_root, archive)

    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    rt.extract_storage(dest_root, archive)
    assert (dest_root / "storage" / "events" / "events.sqlite").read_text() == "data"


def test_extract_storage_rejects_path_traversal(tmp_path: Path) -> None:
    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        member = tarfile.TarInfo(name="../escape.txt")
        payload = b"x"
        import io

        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))
    with pytest.raises(click.ClickException, match="unsafe path"):
        rt.extract_storage(tmp_path / "dest", evil)


def _make_snapshot_dir(base: Path, snapshot_id: str) -> Path:
    snap_dir = base / snapshot_id
    (snap_dir / "volumes").mkdir(parents=True)
    (snap_dir / "volumes" / "postgres_data.tar.gz").write_bytes(b"vol")
    manifest = SnapshotManifest(
        id=snapshot_id,
        # created_at tracks the id so list ordering is deterministic in tests.
        created_at=snapshot_id,
        volumes=["postgres_data"],
    )
    rt.write_manifest(snap_dir, manifest)
    return snap_dir


def test_export_then_import_round_trip(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    rt.snapshots_root(source_root).mkdir(parents=True)
    _make_snapshot_dir(rt.snapshots_root(source_root), "20260630-140509")

    archive = tmp_path / "snap.tar.gz"
    rt.export_snapshot("20260630-140509", archive, root=source_root)
    assert archive.exists()

    dest_root = tmp_path / "dest"
    imported_id = rt.import_snapshot(archive, root=dest_root)
    assert imported_id == "20260630-140509"
    manifest = rt.read_manifest(
        rt.snapshots_root(dest_root) / "20260630-140509"
    )
    assert manifest.volumes == ["postgres_data"]


def test_list_snapshots_sorted_desc_and_skips_invalid(tmp_path: Path) -> None:
    base = rt.snapshots_root(tmp_path)
    base.mkdir(parents=True)
    _make_snapshot_dir(base, "20260101-000000")
    _make_snapshot_dir(base, "20260301-000000")
    # A directory with no manifest is ignored.
    (base / "garbage").mkdir()

    listed = rt.list_snapshots(tmp_path)
    assert [m.id for m in listed] == ["20260301-000000", "20260101-000000"]


def test_delete_snapshot(tmp_path: Path) -> None:
    base = rt.snapshots_root(tmp_path)
    base.mkdir(parents=True)
    _make_snapshot_dir(base, "20260101-000000")
    rt.delete_snapshot("20260101-000000", root=tmp_path)
    assert not (base / "20260101-000000").exists()
    with pytest.raises(click.ClickException, match="not found"):
        rt.delete_snapshot("missing", root=tmp_path)


# --------------------------------------------------------------------------- #
# Orchestration (docker primitives mocked)
# --------------------------------------------------------------------------- #
def test_create_snapshot_stops_archives_and_restarts(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "storage").mkdir()
    compose_calls: list[list[str]] = []
    archived: list[str] = []

    monkeypatch.setattr(rt, "compose_project_name", lambda: "abi")
    monkeypatch.setattr(rt, "volume_exists", lambda name: True)
    monkeypatch.setattr(rt, "current_git_commit", lambda root: "abc1234")
    monkeypatch.setattr(rt, "config_hashes", lambda root: {})
    monkeypatch.setattr(rt, "run_compose", lambda args, **kw: compose_calls.append(args))
    monkeypatch.setattr(
        rt, "archive_volume", lambda volume, dest, key: archived.append(key)
    )
    monkeypatch.setattr(
        rt, "archive_storage", lambda root, dest: Path(dest).write_bytes(b"s")
    )

    manifest = rt.create_snapshot(
        note="pre-migration", now=FIXED_NOW, root=tmp_path, echo=lambda m: None
    )

    assert manifest.id == "20260630-140509"
    assert manifest.note == "pre-migration"
    assert set(manifest.volumes) == set(rt.DATA_VOLUMES)
    assert manifest.storage_included is True
    assert sorted(archived) == sorted(rt.DATA_VOLUMES)
    # Stack is stopped first and restarted afterwards.
    assert ["stop"] in compose_calls
    assert ["up", "-d"] in compose_calls
    assert compose_calls.index(["stop"]) < compose_calls.index(["up", "-d"])
    # Manifest persisted on disk.
    assert (rt.snapshots_root(tmp_path) / manifest.id / "manifest.json").exists()


def test_create_snapshot_errors_when_no_volumes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rt, "compose_project_name", lambda: "abi")
    monkeypatch.setattr(rt, "volume_exists", lambda name: False)
    monkeypatch.setattr(rt, "run_compose", lambda args, **kw: None)
    with pytest.raises(click.ClickException, match="No ABI data volumes"):
        rt.create_snapshot(now=FIXED_NOW, root=tmp_path, echo=lambda m: None)


def test_create_snapshot_cleans_up_and_restarts_on_failure(
    tmp_path: Path, monkeypatch
) -> None:
    compose_calls: list[list[str]] = []
    monkeypatch.setattr(rt, "compose_project_name", lambda: "abi")
    monkeypatch.setattr(rt, "volume_exists", lambda name: True)
    monkeypatch.setattr(rt, "run_compose", lambda args, **kw: compose_calls.append(args))

    def _boom(volume: str, dest: Path, key: str) -> None:
        raise click.ClickException("archive blew up")

    monkeypatch.setattr(rt, "archive_volume", _boom)

    with pytest.raises(click.ClickException, match="archive blew up"):
        rt.create_snapshot(now=FIXED_NOW, root=tmp_path, echo=lambda m: None)

    # Partial snapshot dir removed, stack still restarted.
    assert not (rt.snapshots_root(tmp_path) / "20260630-140509").exists()
    assert ["up", "-d"] in compose_calls


def test_restore_snapshot_takes_safety_snapshot_and_restores(
    tmp_path: Path, monkeypatch
) -> None:
    base = rt.snapshots_root(tmp_path)
    base.mkdir(parents=True)
    snap_dir = _make_snapshot_dir(base, "20260101-000000")
    (snap_dir / "storage.tar.gz").write_bytes(b"s")
    # Mark storage as included in the manifest.
    manifest = rt.read_manifest(snap_dir)
    manifest.storage_included = True
    rt.write_manifest(snap_dir, manifest)

    compose_calls: list[list[str]] = []
    reset: list[str] = []
    extracted: list[str] = []
    safety_calls: list[str] = []

    monkeypatch.setattr(rt, "compose_project_name", lambda: "abi")
    monkeypatch.setattr(rt, "current_git_commit", lambda root: "abc1234")
    monkeypatch.setattr(rt, "config_hashes", lambda root: {})
    monkeypatch.setattr(rt, "volume_exists", lambda name: True)
    monkeypatch.setattr(rt, "run_compose", lambda args, **kw: compose_calls.append(args))
    monkeypatch.setattr(rt, "reset_volume", lambda vol: reset.append(vol))
    monkeypatch.setattr(
        rt, "extract_volume", lambda vol, src, key: extracted.append(key)
    )
    monkeypatch.setattr(rt, "extract_storage", lambda root, src: None)

    def _fake_safety(**kw):
        safety_calls.append(kw.get("slug"))
        return SnapshotManifest(id="20260630-140509-safety", created_at="t")

    monkeypatch.setattr(rt, "create_snapshot", _fake_safety)

    rt.restore_snapshot(
        "20260101-000000", safety=True, now=FIXED_NOW, root=tmp_path, echo=lambda m: None
    )

    assert safety_calls == ["safety"]
    assert reset == ["abi_postgres_data"]
    assert extracted == ["postgres_data"]
    assert ["down"] in compose_calls
    assert ["up", "-d"] in compose_calls


def test_restore_snapshot_can_skip_safety(tmp_path: Path, monkeypatch) -> None:
    base = rt.snapshots_root(tmp_path)
    base.mkdir(parents=True)
    _make_snapshot_dir(base, "20260101-000000")

    safety_calls: list[str] = []
    monkeypatch.setattr(rt, "compose_project_name", lambda: "abi")
    monkeypatch.setattr(rt, "current_git_commit", lambda root: None)
    monkeypatch.setattr(rt, "config_hashes", lambda root: {})
    monkeypatch.setattr(rt, "run_compose", lambda args, **kw: None)
    monkeypatch.setattr(rt, "reset_volume", lambda vol: None)
    monkeypatch.setattr(rt, "extract_volume", lambda vol, src, key: None)

    def _record_safety(**kw):
        safety_calls.append("called")

    monkeypatch.setattr(rt, "create_snapshot", _record_safety)

    rt.restore_snapshot(
        "20260101-000000", safety=False, now=FIXED_NOW, root=tmp_path, echo=lambda m: None
    )
    assert safety_calls == []


# --------------------------------------------------------------------------- #
# Regression tests for review findings
# --------------------------------------------------------------------------- #
def test_extract_storage_clears_stale_files(tmp_path: Path) -> None:
    # Archive captures only a.sqlite.
    source_root = tmp_path / "source"
    (source_root / "storage" / "events").mkdir(parents=True)
    (source_root / "storage" / "events" / "a.sqlite").write_text("SNAP", encoding="utf-8")
    archive = tmp_path / "storage.tar.gz"
    rt.archive_storage(source_root, archive)

    # Destination has an extra file created after the snapshot + a stale a.sqlite.
    dest_root = tmp_path / "dest"
    (dest_root / "storage" / "events").mkdir(parents=True)
    (dest_root / "storage" / "events" / "a.sqlite").write_text("LIVE", encoding="utf-8")
    (dest_root / "storage" / "events" / "b.sqlite").write_text("ORPHAN", encoding="utf-8")

    rt.extract_storage(dest_root, archive)

    assert (dest_root / "storage" / "events" / "a.sqlite").read_text() == "SNAP"
    # The post-snapshot orphan must be gone -- restore is point-in-time.
    assert not (dest_root / "storage" / "events" / "b.sqlite").exists()


def test_import_rejects_colliding_id_and_force_replaces(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    rt.snapshots_root(source_root).mkdir(parents=True)
    _make_snapshot_dir(rt.snapshots_root(source_root), "20260630-140509")
    archive = tmp_path / "snap.tar.gz"
    rt.export_snapshot("20260630-140509", archive, root=source_root)

    dest_root = tmp_path / "dest"
    dest_base = rt.snapshots_root(dest_root)
    dest_base.mkdir(parents=True)
    _make_snapshot_dir(dest_base, "20260630-140509")
    # Give the existing snapshot an extra tarball to prove no silent merge.
    (dest_base / "20260630-140509" / "volumes" / "minio_data.tar.gz").write_bytes(b"x")

    with pytest.raises(click.ClickException, match="already exists locally"):
        rt.import_snapshot(archive, root=dest_root)

    # --force replaces cleanly (the orphan minio tarball must not survive).
    rt.import_snapshot(archive, root=dest_root, force=True)
    assert not (dest_base / "20260630-140509" / "volumes" / "minio_data.tar.gz").exists()


def test_import_rejects_incomplete_archive(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    base = rt.snapshots_root(source_root)
    snap_dir = _make_snapshot_dir(base, "20260630-140509")
    # Manifest claims storage but no storage.tar.gz is present.
    manifest = rt.read_manifest(snap_dir)
    manifest.storage_included = True
    rt.write_manifest(snap_dir, manifest)
    archive = tmp_path / "snap.tar.gz"
    rt.export_snapshot("20260630-140509", archive, root=source_root)

    dest_root = tmp_path / "dest"
    with pytest.raises(click.ClickException, match="incomplete"):
        rt.import_snapshot(archive, root=dest_root)
    # A rejected import leaves nothing behind.
    assert not (rt.snapshots_root(dest_root) / "20260630-140509").exists()


def test_export_rejects_existing_dest_and_force_overwrites(tmp_path: Path) -> None:
    base = rt.snapshots_root(tmp_path)
    base.mkdir(parents=True)
    _make_snapshot_dir(base, "20260630-140509")
    dest = tmp_path / "out.tar.gz"
    dest.write_bytes(b"existing")

    with pytest.raises(click.ClickException, match="already exists"):
        rt.export_snapshot("20260630-140509", dest, root=tmp_path)

    rt.export_snapshot("20260630-140509", dest, root=tmp_path, force=True)
    assert dest.stat().st_size > len(b"existing")


def test_restore_preflight_rejects_missing_volume_tarball(
    tmp_path: Path, monkeypatch
) -> None:
    base = rt.snapshots_root(tmp_path)
    snap_dir = base / "20260101-000000"
    (snap_dir / "volumes").mkdir(parents=True)
    (snap_dir / "volumes" / "postgres_data.tar.gz").write_bytes(b"ok")
    # Manifest lists minio_data too, but its tarball is absent.
    rt.write_manifest(
        snap_dir,
        SnapshotManifest(
            id="20260101-000000",
            created_at="20260101-000000",
            volumes=["postgres_data", "minio_data"],
        ),
    )

    compose_calls: list[list[str]] = []
    reset: list[str] = []
    monkeypatch.setattr(rt, "compose_project_name", lambda: "abi")
    monkeypatch.setattr(rt, "current_git_commit", lambda root: None)
    monkeypatch.setattr(rt, "config_hashes", lambda root: {})
    monkeypatch.setattr(rt, "run_compose", lambda args, **kw: compose_calls.append(args))
    monkeypatch.setattr(rt, "reset_volume", lambda vol: reset.append(vol))

    with pytest.raises(click.ClickException, match="Refusing to restore"):
        rt.restore_snapshot(
            "20260101-000000", now=FIXED_NOW, root=tmp_path, echo=lambda m: None
        )
    # Aborted before any destructive action.
    assert compose_calls == []
    assert reset == []


def test_restore_skips_safety_on_fresh_host(tmp_path: Path, monkeypatch) -> None:
    base = rt.snapshots_root(tmp_path)
    base.mkdir(parents=True)
    _make_snapshot_dir(base, "20260101-000000")

    compose_calls: list[list[str]] = []
    reset: list[str] = []
    safety_calls: list[str] = []
    monkeypatch.setattr(rt, "compose_project_name", lambda: "abi")
    monkeypatch.setattr(rt, "current_git_commit", lambda root: None)
    monkeypatch.setattr(rt, "config_hashes", lambda root: {})
    monkeypatch.setattr(rt, "volume_exists", lambda name: False)  # fresh host
    monkeypatch.setattr(rt, "run_compose", lambda args, **kw: compose_calls.append(args))
    monkeypatch.setattr(rt, "reset_volume", lambda vol: reset.append(vol))
    monkeypatch.setattr(rt, "extract_volume", lambda vol, src, key: None)
    monkeypatch.setattr(
        rt, "create_snapshot", lambda **kw: safety_calls.append("called")
    )

    rt.restore_snapshot(
        "20260101-000000", safety=True, now=FIXED_NOW, root=tmp_path, echo=lambda m: None
    )
    # Safety was skipped (nothing to snapshot) but the restore still ran.
    assert safety_calls == []
    assert reset == ["abi_postgres_data"]
    assert ["up", "-d"] in compose_calls


def test_restore_brings_stack_up_when_extract_fails(tmp_path: Path, monkeypatch) -> None:
    base = rt.snapshots_root(tmp_path)
    base.mkdir(parents=True)
    _make_snapshot_dir(base, "20260101-000000")

    compose_calls: list[list[str]] = []
    monkeypatch.setattr(rt, "compose_project_name", lambda: "abi")
    monkeypatch.setattr(rt, "current_git_commit", lambda root: None)
    monkeypatch.setattr(rt, "config_hashes", lambda root: {})
    monkeypatch.setattr(rt, "volume_exists", lambda name: True)
    monkeypatch.setattr(rt, "run_compose", lambda args, **kw: compose_calls.append(args))
    monkeypatch.setattr(rt, "reset_volume", lambda vol: None)
    monkeypatch.setattr(
        rt,
        "create_snapshot",
        lambda **kw: SnapshotManifest(id="20260101-000000-safety", created_at="t"),
    )

    def _boom(vol, src, key):
        raise click.ClickException("tar truncated")

    monkeypatch.setattr(rt, "extract_volume", _boom)

    with pytest.raises(click.ClickException, match="tar truncated"):
        rt.restore_snapshot(
            "20260101-000000", safety=True, now=FIXED_NOW, root=tmp_path, echo=lambda m: None
        )
    # Stack is brought back up despite the mid-restore failure.
    assert ["down"] in compose_calls
    assert ["up", "-d"] in compose_calls


def test_volume_exists_distinguishes_absent_from_docker_down(monkeypatch) -> None:
    class _Proc:
        def __init__(self, returncode: int, stderr: str = "") -> None:
            self.returncode = returncode
            self.stderr = stderr
            self.stdout = ""

    # returncode 0 -> exists
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **k: _Proc(0))
    assert rt.volume_exists("abi_postgres_data") is True

    # "no such volume" -> genuinely absent
    monkeypatch.setattr(
        rt.subprocess, "run", lambda *a, **k: _Proc(1, "Error: No such volume: x")
    )
    assert rt.volume_exists("x") is False

    # any other error (daemon down) -> raise, do NOT report absent
    monkeypatch.setattr(
        rt.subprocess,
        "run",
        lambda *a, **k: _Proc(1, "Cannot connect to the Docker daemon"),
    )
    with pytest.raises(click.ClickException, match="Docker daemon"):
        rt.volume_exists("x")

    # a generic "not found" (e.g. context error) must NOT be read as absent
    monkeypatch.setattr(
        rt.subprocess, "run", lambda *a, **k: _Proc(1, "context 'foo' not found")
    )
    with pytest.raises(click.ClickException):
        rt.volume_exists("x")


def test_import_dotslash_archive_gives_clean_error(tmp_path: Path) -> None:
    # An archive made with `tar -C dir .` has members '.', './manifest.json', ...
    staging = tmp_path / "staging"
    (staging / "volumes").mkdir(parents=True)
    (staging / "volumes" / "postgres_data.tar.gz").write_bytes(b"x")
    rt.write_manifest(
        staging, SnapshotManifest(id="x", created_at="t", volumes=["postgres_data"])
    )
    archive = tmp_path / "snap.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(staging, arcname=".")

    # Must be a clean ClickException, not an IndexError stacktrace.
    with pytest.raises(click.ClickException, match="single snapshot directory"):
        rt.import_snapshot(archive, root=tmp_path / "dest")


def test_id_taking_commands_reject_traversal_ids(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    rt.snapshots_root(proj).mkdir(parents=True)
    sentinel = proj / "keep.txt"  # would be inside rmtree('..') blast radius
    sentinel.write_text("keep", encoding="utf-8")

    for bad in ("..", "/", "a/b", "."):
        with pytest.raises(click.ClickException, match="Invalid snapshot id"):
            rt.delete_snapshot(bad, root=proj)
        with pytest.raises(click.ClickException, match="Invalid snapshot id"):
            rt.export_snapshot(bad, tmp_path / "o.tar.gz", root=proj)
        with pytest.raises(click.ClickException, match="Invalid snapshot id"):
            rt.restore_snapshot(bad, now=FIXED_NOW, root=proj, echo=lambda m: None)

    # The parent dir and its files are untouched.
    assert sentinel.exists()
    assert rt.snapshots_root(proj).exists()


def _build_snapshot_archive(
    tmp_path: Path,
    dir_name: str,
    *,
    manifest_id: str,
    volumes: list[str],
) -> Path:
    staging = tmp_path / f"staging-{dir_name}"
    (staging / "volumes").mkdir(parents=True)
    for key in volumes:
        (staging / "volumes" / f"{key}.tar.gz").write_bytes(b"x")
    rt.write_manifest(
        staging, SnapshotManifest(id=manifest_id, created_at="t", volumes=volumes)
    )
    archive = tmp_path / f"{dir_name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(staging, arcname=dir_name)
    return archive


def test_import_rejects_manifest_id_mismatch(tmp_path: Path) -> None:
    archive = _build_snapshot_archive(
        tmp_path, "dirX", manifest_id="20260101-000000", volumes=["postgres_data"]
    )
    dest = tmp_path / "dest"
    with pytest.raises(click.ClickException, match="does not match its directory"):
        rt.import_snapshot(archive, root=dest)
    assert not (rt.snapshots_root(dest) / "dirX").exists()


def test_import_rejects_unmanaged_volume(tmp_path: Path) -> None:
    archive = _build_snapshot_archive(
        tmp_path, "20260101-000000", manifest_id="20260101-000000", volumes=["caddy_data"]
    )
    dest = tmp_path / "dest"
    with pytest.raises(click.ClickException, match="does not manage"):
        rt.import_snapshot(archive, root=dest)
    assert not (rt.snapshots_root(dest) / "20260101-000000").exists()


def test_restore_rejects_unmanaged_volume_before_destruction(
    tmp_path: Path, monkeypatch
) -> None:
    base = rt.snapshots_root(tmp_path)
    snap_dir = base / "20260101-000000"
    (snap_dir / "volumes").mkdir(parents=True)
    (snap_dir / "volumes" / "caddy_data.tar.gz").write_bytes(b"x")
    rt.write_manifest(
        snap_dir,
        SnapshotManifest(
            id="20260101-000000", created_at="20260101-000000", volumes=["caddy_data"]
        ),
    )

    compose_calls: list[list[str]] = []
    reset: list[str] = []
    monkeypatch.setattr(rt, "compose_project_name", lambda: "abi")
    monkeypatch.setattr(rt, "run_compose", lambda args, **kw: compose_calls.append(args))
    monkeypatch.setattr(rt, "reset_volume", lambda vol: reset.append(vol))

    with pytest.raises(click.ClickException, match="does not manage"):
        rt.restore_snapshot(
            "20260101-000000", now=FIXED_NOW, root=tmp_path, echo=lambda m: None
        )
    # Nothing destructive ran.
    assert compose_calls == []
    assert reset == []


def _tar_with_member(archive: Path, member_name: str) -> None:
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo(member_name)
        payload = b"x"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))


def test_import_rejects_absolute_top_level_member(tmp_path: Path) -> None:
    # snapshot_id would be '/', collapsing `base / snapshot_id` to '/'.
    archive = tmp_path / "evil_abs.tar.gz"
    _tar_with_member(archive, "/manifest.json")
    proj = tmp_path / "proj"
    with pytest.raises(click.ClickException, match="valid snapshot directory"):
        rt.import_snapshot(archive, root=proj, force=True)


def test_import_rejects_parent_top_level_member(tmp_path: Path) -> None:
    # snapshot_id would be '..', escaping .snapshots/ -> rmtree of the parent.
    archive = tmp_path / "evil_parent.tar.gz"
    _tar_with_member(archive, "../escape.txt")
    proj = tmp_path / "proj"
    rt.snapshots_root(proj).mkdir(parents=True)
    sentinel = proj / "sentinel.txt"  # sibling of .snapshots -> would die on rmtree('..')
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(click.ClickException, match="valid snapshot directory"):
        rt.import_snapshot(archive, root=proj, force=True)
    # Nothing outside the snapshot dir was touched.
    assert sentinel.exists()


def test_extract_storage_rejects_escaping_symlink(tmp_path: Path) -> None:
    archive = tmp_path / "evil.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("storage/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/attacker"  # absolute, escapes dest
        tar.addfile(info)
    with pytest.raises(click.ClickException, match="unsafe link"):
        rt.extract_storage(tmp_path / "dest", archive)


def test_extract_storage_replaces_symlinked_storage(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    (source_root / "storage").mkdir(parents=True)
    (source_root / "storage" / "a.txt").write_text("SNAP", encoding="utf-8")
    archive = tmp_path / "s.tar.gz"
    rt.archive_storage(source_root, archive)

    # Destination storage/ is a symlink to a dir elsewhere (relocated disk).
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    real = tmp_path / "real_storage"
    real.mkdir()
    (real / "stale.txt").write_text("STALE", encoding="utf-8")
    (dest_root / "storage").symlink_to(real)

    rt.extract_storage(dest_root, archive)

    assert not (dest_root / "storage").is_symlink()
    assert (dest_root / "storage" / "a.txt").read_text() == "SNAP"
    assert not (dest_root / "storage" / "stale.txt").exists()

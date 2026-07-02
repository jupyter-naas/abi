"""Point-in-time snapshots of the Docker stack's stateful data.

This module owns the *logic* for capturing, restoring, and moving snapshots of
the local Docker Compose deployment described by ``config.local.yaml``. The
Click surface lives in :mod:`naas_abi_cli.cli.snapshot` and is intentionally
thin so this logic stays unit-testable.

What is captured:
  * the stateful Docker volumes (``postgres_data``, ``minio_data``,
    ``fuseki_data``, ``qdrant_storage``, ``redis_data``, ``rabbitmq_data``,
    ``headscale_data``) -- copied cold as raw tarballs so each engine's on-disk
    state is consistent;
  * the host ``storage/`` directory (the durable SQLite event log + local
    datastore files).

Transient volumes (caddy certs, dagster run history, build/model caches, and
the headscale ``headscale_run`` socket dir) are skipped -- they rebuild
themselves.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import click

from .bootstrap import find_abi_project_root
from .stack_runtime import run_compose

# Stateful volumes worth snapshotting, by their docker-compose volume key.
# redis runs with --appendonly yes (durable KV, not just a cache); rabbitmq
# holds durable queues (see the hostname note in docker-compose.yml -- the node
# name must be stable for its data to survive a restore); headscale_data holds
# the users/nodes SQLite DB + noise key. The headscale_run socket dir, caddy
# certs, dagster run history, and build/model caches are intentionally excluded.
DATA_VOLUMES: tuple[str, ...] = (
    "postgres_data",
    "minio_data",
    "fuseki_data",
    "qdrant_storage",
    "redis_data",
    "rabbitmq_data",
    "headscale_data",
)

SNAPSHOTS_DIRNAME = ".snapshots"
MANIFEST_NAME = "manifest.json"
STORAGE_DIRNAME = "storage"
VOLUMES_DIRNAME = "volumes"
# Tiny, ubiquitous image used purely to tar/untar volume contents.
HELPER_IMAGE = "alpine:3.20"
# Files whose content we fingerprint so we can warn about drift on restore.
TRACKED_CONFIG_FILES = ("config.local.yaml", ".env")
MANIFEST_FORMAT_VERSION = 1


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #
@dataclass
class SnapshotManifest:
    """Metadata persisted alongside every snapshot's tarballs."""

    id: str
    created_at: str
    note: str = ""
    project: str = ""
    git_commit: str | None = None
    cli_version: str = "unknown"
    volumes: list[str] = field(default_factory=list)
    storage_included: bool = False
    config_hashes: dict[str, str] = field(default_factory=dict)
    size_bytes: int = 0
    format_version: int = MANIFEST_FORMAT_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> "SnapshotManifest":
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("manifest must be a JSON object")
        known = {f for f in cls.__dataclass_fields__}  # noqa: C416
        return cls(**{k: v for k, v in data.items() if k in known})


# --------------------------------------------------------------------------- #
# Pure helpers (no side effects -- the easy-to-test core)
# --------------------------------------------------------------------------- #
def sanitize_slug(text: str) -> str:
    """Reduce arbitrary text to a filesystem/id-safe slug."""
    out: list[str] = []
    for ch in text.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {" ", "-", "_"}:
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def generate_snapshot_id(now: datetime, slug: str | None = None) -> str:
    stamp = now.strftime("%Y%m%d-%H%M%S")
    if slug:
        clean = sanitize_slug(slug)
        if clean:
            return f"{stamp}-{clean}"
    return stamp


def sanitize_project_name(name: str) -> str:
    """Mimic docker compose's project-name normalisation."""
    lowered = name.lower()
    cleaned = "".join(ch for ch in lowered if ch.isalnum() or ch in {"_", "-"})
    return cleaned.lstrip("_-")


def parse_project_name(config_json: str) -> str | None:
    """Extract the resolved project ``name`` from ``compose config --format json``."""
    try:
        data = json.loads(config_json)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    return str(name) if name else None


def volume_full_name(project: str, key: str) -> str:
    return f"{project}_{key}"


def select_prunable(manifests: list[SnapshotManifest], keep: int) -> list[str]:
    """Return ids of snapshots to delete, keeping the ``keep`` newest."""
    if keep < 0:
        raise ValueError("keep must be >= 0")
    ordered = sorted(manifests, key=lambda m: m.created_at, reverse=True)
    return [m.id for m in ordered[keep:]]


def detect_drift(
    manifest: SnapshotManifest,
    current_commit: str | None,
    current_hashes: dict[str, str],
) -> list[str]:
    """Human-readable warnings when code/config differs from snapshot time."""
    messages: list[str] = []
    if (
        manifest.git_commit
        and current_commit
        and manifest.git_commit != current_commit
    ):
        messages.append(
            f"git commit differs: snapshot {manifest.git_commit} vs current "
            f"{current_commit}"
        )
    for name, snapshot_hash in manifest.config_hashes.items():
        current = current_hashes.get(name)
        if current and current != snapshot_hash:
            messages.append(f"{name} has changed since the snapshot was taken")
    return messages


# --------------------------------------------------------------------------- #
# Filesystem layout
# --------------------------------------------------------------------------- #
def project_root() -> Path:
    return find_abi_project_root() or Path.cwd()


def snapshots_root(root: Path) -> Path:
    return root / SNAPSHOTS_DIRNAME


def _is_unsafe_component(name: str) -> bool:
    """True if ``name`` is not a single, plain path component.

    Anything absolute ('/'), a parent ref ('..'), '.', empty, or containing a
    separator would make ``base / name`` resolve outside the snapshots dir --
    dangerous because delete/restore/import act destructively on that path.
    """
    return (not name) or name in (".", "..") or Path(name).name != name


def _validate_snapshot_id(snapshot_id: str) -> str:
    if _is_unsafe_component(snapshot_id):
        raise click.ClickException(f"Invalid snapshot id: '{snapshot_id}'.")
    return snapshot_id


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def config_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in TRACKED_CONFIG_FILES:
        digest = _sha256_file(root / name)
        if digest:
            hashes[name] = digest
    return hashes


def dir_size(path: Path) -> int:
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                continue
    return total


def cli_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("naas-abi-cli")
        except PackageNotFoundError:
            return "unknown"
    except Exception:
        return "unknown"


def current_git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def write_manifest(snap_dir: Path, manifest: SnapshotManifest) -> None:
    (snap_dir / MANIFEST_NAME).write_text(manifest.to_json(), encoding="utf-8")


def read_manifest(snap_dir: Path) -> SnapshotManifest:
    manifest_path = snap_dir / MANIFEST_NAME
    if not manifest_path.exists():
        raise click.ClickException(f"No snapshot manifest at {manifest_path}.")
    try:
        return SnapshotManifest.from_json(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, TypeError) as error:
        raise click.ClickException(
            f"Snapshot manifest at {manifest_path} is invalid: {error}"
        ) from error


# --------------------------------------------------------------------------- #
# Docker primitives (side-effecting -- mocked in tests)
# --------------------------------------------------------------------------- #
def run_docker(
    args: list[str], capture_output: bool = False
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["docker", *args],
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except FileNotFoundError as error:
        raise click.ClickException(
            "Docker is not installed or not available in PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        raise click.ClickException(
            f"docker {' '.join(args)} failed with exit code {error.returncode}."
        ) from error


def compose_project_name() -> str:
    """Resolve the compose project name (the volume prefix).

    Primary source is ``docker compose config --format json`` -- it honours
    ``COMPOSE_PROJECT_NAME`` and ``.env``. Falls back to the env var, then to a
    normalised project-directory name so the command still works when the stack
    is fully down.
    """
    try:
        result = run_compose(["config", "--format", "json"], capture_output=True)
        name = parse_project_name(result.stdout or "")
        if name:
            return name
    except click.ClickException:
        pass

    env_name = os.environ.get("COMPOSE_PROJECT_NAME")
    if env_name:
        return sanitize_project_name(env_name)

    return sanitize_project_name(project_root().name)


def volume_exists(name: str) -> bool:
    """True if the named volume exists; raise if docker itself is unreachable.

    ``docker volume inspect`` exits non-zero both when a volume is genuinely
    absent and when the daemon is down / unreachable. We must not treat the
    latter as "absent" -- otherwise create would report "no data volumes found"
    when the real problem is a stopped Docker. Only a "no such volume" stderr
    means absent; anything else re-raises.
    """
    try:
        result = subprocess.run(
            ["docker", "volume", "inspect", name],
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as error:
        raise click.ClickException(
            "Docker is not installed or not available in PATH."
        ) from error
    if result.returncode == 0:
        return True
    stderr = (result.stderr or "").lower()
    # Only the exact "no such volume" message means genuinely absent. A broader
    # match (e.g. "not found") would misread docker context/daemon errors as
    # "volume absent" and silently skip work or the safety snapshot.
    if "no such volume" in stderr:
        return False
    raise click.ClickException(
        f"Could not query docker volume '{name}': "
        f"{(result.stderr or 'docker error').strip()}. Is the Docker daemon running?"
    )


def _chown_to_host(target: str) -> str:
    """Shell fragment handing helper-written output back to the host user.

    The helper runs as root so it can read arbitrary volume/app-written files;
    on Linux bind mounts that makes its output root-owned and unreadable to the
    non-root host user running the CLI, which would break a later host-side
    export/read. chown fixes it. No-op where the platform has no uid concept.
    """
    if hasattr(os, "getuid"):
        return f" && chown -R {os.getuid()}:{os.getgid()} {target}"
    return ""


def archive_volume(volume: str, dest_dir: Path, key: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    tarball = f"/to/{key}.tar.gz"
    # --mount long-form (not -v) so host paths containing ':' are unambiguous.
    # Runs as root (to read any volume contents), then chowns the tarball back to
    # the host user so `export`/`list` can read it.
    run_docker(
        [
            "run",
            "--rm",
            "--mount",
            f"type=volume,source={volume},destination=/from,readonly",
            "--mount",
            f"type=bind,source={dest_dir.resolve()},destination=/to",
            HELPER_IMAGE,
            "sh",
            "-c",
            f"tar czf {tarball} -C /from ." + _chown_to_host(tarball),
        ]
    )


def extract_volume(volume: str, src_dir: Path, key: str) -> None:
    run_docker(
        [
            "run",
            "--rm",
            "--mount",
            f"type=volume,source={volume},destination=/to",
            "--mount",
            f"type=bind,source={src_dir.resolve()},destination=/from,readonly",
            HELPER_IMAGE,
            "sh",
            "-c",
            f"cd /to && tar xzf /from/{key}.tar.gz",
        ]
    )


def reset_volume(volume: str) -> None:
    """Empty a volume in place so a restore lands on pristine contents.

    Contents are cleared rather than the volume being removed/recreated, so the
    compose-managed volume and its labels stay intact (a manually recreated
    volume can make ``docker compose up`` complain about external volumes). A
    non-existent named volume is auto-created empty by the mount.
    """
    run_docker(
        [
            "run",
            "--rm",
            "--mount",
            f"type=volume,source={volume},destination=/to",
            HELPER_IMAGE,
            "sh",
            "-c",
            "find /to -mindepth 1 -delete",
        ]
    )


# --------------------------------------------------------------------------- #
# Tar helpers for the host storage/ dir and snapshot export/import
# --------------------------------------------------------------------------- #
def archive_storage(root: Path, dest_file: Path) -> None:
    storage_dir = root / STORAGE_DIRNAME
    # Tar storage/ inside the root helper, not host-side Python: the app container
    # writes files here as root, which the non-root host user often cannot read.
    # `.resolve()` follows a symlinked storage/ so we capture its contents.
    source = storage_dir.resolve()
    out = f"/out/{dest_file.name}"
    run_docker(
        [
            "run",
            "--rm",
            "--mount",
            f"type=bind,source={source},destination=/data/{STORAGE_DIRNAME},readonly",
            "--mount",
            f"type=bind,source={dest_file.parent.resolve()},destination=/out",
            HELPER_IMAGE,
            "sh",
            "-c",
            f"tar czf {out} -C /data {STORAGE_DIRNAME}" + _chown_to_host(out),
        ]
    )


def _assert_safe_members(tar: tarfile.TarFile, dest: Path) -> None:
    """Reject archive members -- and link targets -- that escape ``dest``.

    Guards plain path traversal AND symlink/hardlink members whose target points
    outside dest. The link check matters because the Python 3.11.0-3.11.3
    fallback in ``_safe_extract`` extracts without the built-in ``data``
    filter, so it would otherwise honour an escaping link.
    """
    dest_resolved = dest.resolve()

    def _within(path: Path) -> bool:
        resolved = path.resolve()
        return resolved == dest_resolved or dest_resolved in resolved.parents

    for member in tar.getmembers():
        if not _within(dest_resolved / member.name):
            raise click.ClickException(
                f"Refusing to extract unsafe path from archive: {member.name}"
            )
        if member.issym() or member.islnk():
            if member.issym():
                link_target = (
                    dest_resolved / os.path.dirname(member.name) / member.linkname
                )
            else:  # hardlink target is relative to the archive root
                link_target = dest_resolved / member.linkname
            if os.path.isabs(member.linkname) or not _within(link_target):
                raise click.ClickException(
                    "Refusing to extract unsafe link from archive: "
                    f"{member.name} -> {member.linkname}"
                )


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract with the 3.12 data filter, falling back for Python 3.11.0-3.11.3.

    The ``filter`` kwarg only landed in 3.11.4; our requires-python allows
    earlier 3.11.x. ``_assert_safe_members`` guards path traversal *and* escaping
    link targets, so the unfiltered fallback stays safe.
    """
    _assert_safe_members(tar, dest)
    try:
        tar.extractall(dest, filter="data")
    except TypeError:
        # Safe: _assert_safe_members above already rejected any traversal or
        # escaping-link members, which is exactly what the "data" filter enforces.
        tar.extractall(dest)  # nosec B202


def extract_storage(root: Path, src_file: Path) -> None:
    # Validate member paths (and link targets) on the host first -- the guard
    # `_safe_extract` would otherwise apply -- then clear + extract inside the
    # root helper. The helper is needed because storage/ can contain root-owned
    # files/dirs the host user cannot remove. Clearing first keeps restore a
    # faithful point-in-time copy (no stale post-snapshot files survive).
    with tarfile.open(src_file, "r:gz") as tar:
        _assert_safe_members(tar, root)
    dest_storage = f"/dest/{STORAGE_DIRNAME}"
    run_docker(
        [
            "run",
            "--rm",
            "--mount",
            f"type=bind,source={root.resolve()},destination=/dest",
            "--mount",
            f"type=bind,source={src_file.parent.resolve()},destination=/in,readonly",
            HELPER_IMAGE,
            "sh",
            "-c",
            f"rm -rf {dest_storage} && tar xzf /in/{src_file.name} -C /dest",
        ]
    )


def _snapshot_artifacts_ok(snap_dir: Path, manifest: SnapshotManifest) -> list[str]:
    """Return a list of missing-artifact messages for a snapshot dir (empty=ok)."""
    problems: list[str] = []
    for key in manifest.volumes:
        tarball = snap_dir / VOLUMES_DIRNAME / f"{key}.tar.gz"
        if not tarball.exists():
            problems.append(f"missing volume archive for '{key}' ({tarball.name})")
    if manifest.storage_included and not (snap_dir / "storage.tar.gz").exists():
        problems.append("manifest says storage was captured but storage.tar.gz is missing")
    return problems


def export_snapshot(
    snapshot_id: str, dest: Path, root: Path | None = None, force: bool = False
) -> Path:
    _validate_snapshot_id(snapshot_id)
    root = root or project_root()
    snap_dir = snapshots_root(root) / snapshot_id
    read_manifest(snap_dir)  # validate it exists and is well-formed
    dest = Path(dest)
    if dest.exists() and not force:
        raise click.ClickException(
            f"Destination '{dest}' already exists. Use --force to overwrite."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w:gz") as tar:
        tar.add(snap_dir, arcname=snapshot_id)
    return dest


def import_snapshot(src: Path, root: Path | None = None, force: bool = False) -> str:
    root = root or project_root()
    src = Path(src)
    if not src.exists():
        raise click.ClickException(f"Archive not found: {src}")
    base = snapshots_root(root)
    base.mkdir(parents=True, exist_ok=True)
    with tarfile.open(src, "r:gz") as tar:
        # Skip members with no path parts ('.', './', '') so a `tar -C dir .`
        # style archive resolves to its real top-level entries instead of raising
        # IndexError on Path('.').parts[0].
        top_levels = {
            parts[0] for m in tar.getmembers() if (parts := Path(m.name).parts)
        }
        if len(top_levels) != 1:
            raise click.ClickException(
                "Archive does not contain a single snapshot directory."
            )
        snapshot_id = next(iter(top_levels))
        # The snapshot id must be a single, plain directory name. A member rooted
        # at '/' collapses `base / snapshot_id` to '/', and '..' escapes the
        # snapshots dir -- either would make the shutil.rmtree below catastrophic
        # (rmtree of '/' or the project dir) on a malicious/malformed archive.
        if _is_unsafe_component(snapshot_id):
            raise click.ClickException(
                "Archive does not contain a valid snapshot directory."
            )
        dest_dir = base / snapshot_id
        # Defense in depth: dest_dir must be a direct child of the snapshots dir.
        if dest_dir.resolve().parent != base.resolve():
            raise click.ClickException(
                "Archive does not contain a valid snapshot directory."
            )
        if dest_dir.exists():
            # Never merge onto an existing snapshot -- tar would overwrite some
            # files and leave others orphaned, producing a dir that no longer
            # matches its own manifest.
            if not force:
                raise click.ClickException(
                    f"Snapshot '{snapshot_id}' already exists locally. "
                    "Delete it first or pass --force to replace it."
                )
            shutil.rmtree(dest_dir)
        _safe_extract(tar, base)
    manifest = read_manifest(dest_dir)  # validate JSON
    problems = _snapshot_artifacts_ok(dest_dir, manifest)
    if problems:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise click.ClickException(
            "Imported archive is incomplete: " + "; ".join(problems)
        )
    # The manifest id must match the directory name -- list_snapshots reports
    # manifest.id while restore/delete/export/prune locate by directory name, so a
    # mismatch makes the snapshot unusable (and could point prune at the wrong dir).
    if manifest.id != snapshot_id:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise click.ClickException(
            f"Imported archive is inconsistent: manifest id '{manifest.id}' does "
            f"not match its directory '{snapshot_id}'."
        )
    # Only ever manage the known data volumes -- a crafted manifest must not make
    # restore wipe an out-of-band host volume.
    unknown = [k for k in manifest.volumes if k not in DATA_VOLUMES]
    if unknown:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise click.ClickException(
            "Imported archive lists volumes ABI does not manage: "
            + ", ".join(unknown)
        )
    return snapshot_id


# --------------------------------------------------------------------------- #
# High-level orchestration
# --------------------------------------------------------------------------- #
def list_snapshots(root: Path | None = None) -> list[SnapshotManifest]:
    base = snapshots_root(root or project_root())
    if not base.exists():
        return []
    manifests: list[SnapshotManifest] = []
    for entry in base.iterdir():
        if not entry.is_dir() or not (entry / MANIFEST_NAME).exists():
            continue
        try:
            manifests.append(read_manifest(entry))
        except click.ClickException:
            continue
    manifests.sort(key=lambda m: m.created_at, reverse=True)
    return manifests


def delete_snapshot(snapshot_id: str, root: Path | None = None) -> None:
    _validate_snapshot_id(snapshot_id)
    base = snapshots_root(root or project_root())
    snap_dir = base / snapshot_id
    if not snap_dir.exists():
        raise click.ClickException(f"Snapshot '{snapshot_id}' not found.")
    shutil.rmtree(snap_dir)


def create_snapshot(
    *,
    note: str = "",
    slug: str | None = None,
    now: datetime,
    root: Path | None = None,
    echo: Callable[[str], None] | None = None,
) -> SnapshotManifest:
    emit = echo if echo is not None else click.echo
    root = root or project_root()
    project = compose_project_name()

    present = [k for k in DATA_VOLUMES if volume_exists(volume_full_name(project, k))]
    if not present:
        raise click.ClickException(
            f"No ABI data volumes found for project '{project}'. "
            "Verify the running stack with 'docker volume ls'."
        )
    missing = [k for k in DATA_VOLUMES if k not in present]
    if missing:
        emit(f"Note: skipping volumes not present on this stack: {', '.join(missing)}")

    snapshot_id = generate_snapshot_id(now, slug)
    snap_dir = snapshots_root(root) / snapshot_id
    if snap_dir.exists():
        raise click.ClickException(f"Snapshot '{snapshot_id}' already exists.")
    volumes_dir = snap_dir / VOLUMES_DIRNAME
    volumes_dir.mkdir(parents=True)

    emit("Stopping stack for a consistent copy...")
    run_compose(["stop"])
    try:
        try:
            for key in present:
                emit(f"  - archiving volume {key}")
                archive_volume(volume_full_name(project, key), volumes_dir, key)

            storage_dir = root / STORAGE_DIRNAME
            storage_included = storage_dir.exists()
            if storage_included:
                emit("  - archiving storage/")
                archive_storage(root, snap_dir / "storage.tar.gz")

            manifest = SnapshotManifest(
                id=snapshot_id,
                created_at=now.isoformat(),
                note=note,
                project=project,
                git_commit=current_git_commit(root),
                cli_version=cli_version(),
                volumes=present,
                storage_included=storage_included,
                config_hashes=config_hashes(root),
                size_bytes=dir_size(snap_dir),
            )
            write_manifest(snap_dir, manifest)
        except BaseException:
            shutil.rmtree(snap_dir, ignore_errors=True)
            raise
    finally:
        # `up -d` (not `start`) so the stack is brought back even if it had been
        # fully `down` (volumes retained) rather than merely stopped.
        emit("Restarting stack...")
        run_compose(["up", "-d"])

    return manifest


def restore_snapshot(
    snapshot_id: str,
    *,
    safety: bool = True,
    now: datetime,
    root: Path | None = None,
    echo: Callable[[str], None] | None = None,
) -> SnapshotManifest:
    emit = echo if echo is not None else click.echo
    _validate_snapshot_id(snapshot_id)
    root = root or project_root()
    snap_dir = snapshots_root(root) / snapshot_id
    manifest = read_manifest(snap_dir)
    project = compose_project_name()

    # Pre-flight: validate BEFORE any destructive step so a corrupt/incomplete or
    # tampered snapshot aborts without having wiped a live volume.
    # Allowlist first: never wipe/overwrite a volume outside the managed set even
    # if a hand-crafted (imported) manifest names one.
    unknown = [k for k in manifest.volumes if k not in DATA_VOLUMES]
    if unknown:
        raise click.ClickException(
            f"Refusing to restore '{snapshot_id}': it lists volumes ABI does not "
            f"manage ({', '.join(unknown)})."
        )
    problems = _snapshot_artifacts_ok(snap_dir, manifest)
    if problems:
        raise click.ClickException(
            f"Refusing to restore '{snapshot_id}': " + "; ".join(problems)
        )

    drift = detect_drift(manifest, current_git_commit(root), config_hashes(root))
    for message in drift:
        emit(f"Warning: {message}")

    # Safety snapshot -- best-effort. On a fresh host (import -> restore) there is
    # nothing to snapshot yet, so skip rather than abort the whole restore.
    safety_id: str | None = None
    if safety:
        if any(volume_exists(volume_full_name(project, k)) for k in DATA_VOLUMES):
            emit("Taking a safety snapshot of the current state first...")
            safety_id = create_snapshot(
                note=f"auto-safety before restore of {snapshot_id}",
                slug="safety",
                now=now,
                root=root,
                echo=emit,
            ).id
        else:
            emit("No existing stack data found; skipping safety snapshot.")

    emit(f"Restoring snapshot {snapshot_id}...")
    run_compose(["down"])
    try:
        for key in manifest.volumes:
            volume = volume_full_name(project, key)
            emit(f"  - restoring volume {key}")
            reset_volume(volume)
            extract_volume(volume, snap_dir / VOLUMES_DIRNAME, key)

        if manifest.storage_included:
            emit("  - restoring storage/")
            extract_storage(root, snap_dir / "storage.tar.gz")
    except BaseException:
        # A failure here can leave volumes half-restored. Never leave the stack
        # down, and tell the operator how to recover from the safety snapshot.
        emit("ERROR: restore failed partway through; stack data may be inconsistent.")
        if safety_id:
            emit(
                "Recover the previous state with: "
                f"abi stack snapshot restore {safety_id} --no-safety-snapshot"
            )
        try:
            run_compose(["up", "-d"])
        except click.ClickException:
            pass
        raise

    emit("Starting stack...")
    run_compose(["up", "-d"])
    return manifest

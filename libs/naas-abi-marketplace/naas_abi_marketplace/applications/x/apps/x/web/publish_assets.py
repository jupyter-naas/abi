"""Upload the Next.js static export under ``web/out/`` to object storage."""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.applications.x.apps.x.api.common import (
    content_digest,
    encode_compact,
)

# Per-file digests of the last upload, so a republish only PUTs what changed.
# Kept outside the export's own layout (Next never emits a ``web/`` directory)
# so it can never collide with a real asset.
_MANIFEST_DIR = "web"
_MANIFEST_NAME = "manifest.json"

WEB_DIR = Path(__file__).resolve().parent
# Next.js basePath only rewrites asset URLs; export files land in out/ directly.
EXPORT_DIR = WEB_DIR / "out"
# The deploy image builds the export in a Node stage and copies it here — under
# /opt, because compose bind-mounts the repo over /app and would hide a baked
# copy living inside it. Overridable with X_APP_WEB_EXPORT_DIR.
BAKED_EXPORT_DIR = Path("/opt/x-app-web/out")

# Extensions we expect from a Next static export.
# ``index.txt`` is kept: it is the router payload the browser fetches when
# moving between the app's pages, and without it every click is a full reload.
_SKIP_NAMES = {".DS_Store"}
_SKIP_PREFIXES = ("404/",)


def _is_export(path: Path) -> bool:
    return path.is_dir() and (path / "index.html").is_file()


def export_candidates() -> list[Path]:
    """Where an export may live, most specific first.

    A locally built ``web/out/`` wins over the image-baked copy, so a developer
    who just ran ``pnpm build`` publishes what they built; ``X_APP_WEB_EXPORT_DIR``
    overrides both when set.
    """
    candidates: list[Path] = []
    override = os.environ.get("X_APP_WEB_EXPORT_DIR")
    if override:
        candidates.append(Path(override))
    candidates.append(EXPORT_DIR)
    if BAKED_EXPORT_DIR not in candidates:
        candidates.append(BAKED_EXPORT_DIR)
    return candidates


def resolve_export_dir() -> Path | None:
    """First candidate that actually holds an export, or ``None``."""
    for candidate in export_candidates():
        if _is_export(candidate):
            return candidate
    return None


def web_export_dir() -> Path:
    return resolve_export_dir() or EXPORT_DIR


def web_export_exists() -> bool:
    """Whether a usable Next export is reachable on this filesystem."""
    return resolve_export_dir() is not None


def ensure_web_built() -> Path:
    """Return the export dir or raise with a clear rebuild hint."""
    resolved = resolve_export_dir()
    if resolved is None:
        looked = ", ".join(str(c) for c in export_candidates())
        raise FileNotFoundError(
            f"X web static export missing (looked in: {looked}). "
            "From applications/x/apps/x/web run: pnpm install && pnpm build"
        )
    return resolved


def upload_web_export(
    object_storage: ObjectStorageService,
    app_prefix: str,
    *,
    required: bool = True,
) -> dict:
    """Copy every file from the Next export into ``app_prefix/``.

    ``out/`` is a build artifact: it is gitignored, so a fresh checkout has none.
    The deploy image builds it in a Node stage (see
    ``.deploy/docker/images/Dockerfile``) and exposes it through
    ``X_APP_WEB_EXPORT_DIR``. With *required* false a missing export is
    therefore not an error — the JSON snapshots (which need no build step) are
    still published and whatever web assets object storage already holds stay
    in place. Only a caller that just ran ``pnpm build`` should demand it.
    """
    if not required and not web_export_exists():
        looked = ", ".join(str(c) for c in export_candidates())
        logger.warning(
            f"X app publish: no web export (looked in: {looked}) — snapshots "
            "published, web assets left as-is. Rebuild the deploy image, or run "
            "`pnpm build` in apps/x/web on a host with Node."
        )
        return {
            "skipped": True,
            "reason": "web export missing",
            "looked_in": looked,
        }
    root = ensure_web_built()
    prefix = app_prefix.rstrip("/")
    previous = _read_manifest(object_storage, prefix)
    manifest: dict[str, str] = {}
    uploaded: list[str] = []
    unchanged = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in _SKIP_NAMES:
            continue
        rel = path.relative_to(root).as_posix()
        if rel == "404.html" or rel.startswith(_SKIP_PREFIXES):
            continue
        if "/" in rel:
            subdir, name = rel.rsplit("/", 1)
            put_prefix = f"{prefix}/{subdir}"
        else:
            put_prefix = prefix
            name = rel
        content = path.read_bytes()
        digest = content_digest(content)
        manifest[rel] = digest
        # Most of the export is ``_next/static/**``, whose file names are already
        # content-hashed — those bytes are identical on every publish.
        if previous.get(rel) == digest:
            unchanged += 1
            continue
        object_storage.put_object(put_prefix, name, content)
        uploaded.append(f"{put_prefix}/{name}")
        logger.debug(
            f"X web upload: {put_prefix}/{name} "
            f"({len(content)} bytes, {mimetypes.guess_type(name)[0] or 'bin'})"
        )

    if manifest != previous:
        object_storage.put_object(
            f"{prefix}/{_MANIFEST_DIR}", _MANIFEST_NAME, encode_compact(manifest)
        )

    summary = {
        "export_dir": str(root),
        "files": len(manifest),
        "uploaded": len(uploaded),
        "unchanged": unchanged,
        "index_file": f"{prefix}/index.html",
    }
    logger.info(f"X web upload_web_export: done — {summary}")
    return summary


def _read_manifest(object_storage: ObjectStorageService, prefix: str) -> dict[str, str]:
    """Digests from the previous upload, ``{}`` when absent or unreadable.

    Failing to an empty manifest re-uploads everything, which is exactly the
    pre-existing behaviour — never a reason to fail the publish.
    """
    try:
        raw = object_storage.get_object(f"{prefix}/{_MANIFEST_DIR}", _MANIFEST_NAME)
    except Exception:  # noqa: BLE001 — absent on a first publish
        return {}
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    if not isinstance(decoded, dict):
        return {}
    return {str(k): str(v) for k, v in decoded.items()}


def maybe_build_web(*, force: bool = False) -> Path | None:
    """Optionally run ``pnpm``/``npm`` build when export is missing (or *force*)."""
    if not force and EXPORT_DIR.is_dir() and (EXPORT_DIR / "index.html").is_file():
        return EXPORT_DIR

    if not (WEB_DIR / "package.json").is_file():
        return None

    import subprocess

    env = os.environ.copy()
    install_cmds = (
        ["pnpm", "install", "--frozen-lockfile"],
        ["pnpm", "install"],
        ["npm", "ci"],
        ["npm", "install"],
    )
    installed = False
    for cmd in install_cmds:
        try:
            subprocess.run(cmd, cwd=WEB_DIR, check=True, env=env)
            installed = True
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    if not installed:
        raise RuntimeError("Could not install X web dependencies (pnpm/npm)")

    for cmd in (["pnpm", "build"], ["npm", "run", "build"]):
        try:
            subprocess.run(cmd, cwd=WEB_DIR, check=True, env=env)
            break
        except FileNotFoundError:
            continue
    else:
        raise RuntimeError("Could not build X web (pnpm/npm)")

    return ensure_web_built()

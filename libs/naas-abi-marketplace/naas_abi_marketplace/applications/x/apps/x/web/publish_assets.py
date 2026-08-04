"""Upload the Next.js static export under ``web/out/`` to object storage."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

WEB_DIR = Path(__file__).resolve().parent
# Next.js basePath only rewrites asset URLs; export files land in out/ directly.
EXPORT_DIR = WEB_DIR / "out"

# Extensions we expect from a Next static export.
_SKIP_NAMES = {".DS_Store", "index.txt"}
_SKIP_PREFIXES = ("404/",)


def web_export_dir() -> Path:
    return EXPORT_DIR


def ensure_web_built() -> Path:
    """Return the export dir or raise with a clear rebuild hint."""
    if not EXPORT_DIR.is_dir() or not (EXPORT_DIR / "index.html").is_file():
        raise FileNotFoundError(
            f"X web static export missing at {EXPORT_DIR}. "
            "From applications/x/apps/x/web run: pnpm install && pnpm build"
        )
    return EXPORT_DIR


def upload_web_export(
    object_storage: ObjectStorageService,
    app_prefix: str,
) -> dict:
    """Copy every file from the Next export into ``app_prefix/``."""
    root = ensure_web_built()
    prefix = app_prefix.rstrip("/")
    uploaded: list[str] = []

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
        object_storage.put_object(put_prefix, name, content)
        uploaded.append(f"{put_prefix}/{name}")
        logger.debug(
            f"X web upload: {put_prefix}/{name} "
            f"({len(content)} bytes, {mimetypes.guess_type(name)[0] or 'bin'})"
        )

    summary = {
        "export_dir": str(root),
        "files": len(uploaded),
        "index_file": f"{prefix}/index.html",
    }
    logger.info(f"X web upload_web_export: done — {summary}")
    return summary


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

#!/usr/bin/env python3
"""Local dev server: the People Search API plus the static app.

Run it from the domain Makefile (``make people``), or directly. It serves the
same routes the module mounts inside Nexus, so what works here works there.

``--config`` (or ``PEOPLE_APP_CONFIG``) runs another instance: its own brand,
its own tables, its own ``web/index.html`` and ``web/assets/``, on the
renderers shipped with this package.
"""

from __future__ import annotations

import argparse
import errno
import os
import socket
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from naas_abi_marketplace.domains.personnel.apps.people.api.mount import (
    mount_people_app,
)
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import (
    ConfigError,
    public_config,
    web_root_for,
)
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles

DEFAULT_PREFIX = "/api/personnel-people"


class DevStaticFiles(StaticFiles):
    """Local dev: skip 304 Not Modified so a normal reload picks up JS/CSS edits."""

    def file_response(
        self,
        full_path,
        stat_result,
        scope,
        status_code: int = 200,
    ) -> Response:
        response = FileResponse(
            full_path, status_code=status_code, stat_result=stat_result
        )
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response


class DevSharedFiles(StaticFiles):
    """The shared renderers, with the same no-cache behaviour as the page."""

    file_response = DevStaticFiles.file_response


def create_app(
    config_path: Path | None = None, *, prefix: str = DEFAULT_PREFIX
) -> FastAPI:
    config = public_config(config_path)
    app = FastAPI(title=config["brand"]["name"])
    mount_people_app(app, prefix=prefix, config_path=config_path)
    # The instance's own files last, at the root: brand files and portraits live
    # under its web/assets/, so the paths in config.yaml resolve the same way
    # here and inside Nexus. Mounted after the API so /api/... is not shadowed.
    app.mount(
        "/",
        DevStaticFiles(directory=web_root_for(config_path), html=True),
        name="web",
    )
    return app


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError as exc:
            return exc.errno in (errno.EADDRINUSE, errno.EACCES)
    return False


def _find_free_port(host: str, preferred: int, *, scan: int = 100) -> int:
    if not _port_in_use(host, preferred):
        return preferred
    for offset in range(1, scan + 1):
        candidate = preferred + offset
        if not _port_in_use(host, candidate):
            return candidate
    raise SystemExit(
        f"No free port found in range {preferred}..{preferred + scan} on {host}"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=os.environ.get("PEOPLE_APP_CONFIG") or None,
        help="config.yaml of the instance to serve (default: the one shipped here)",
    )
    parser.add_argument(
        "--api-prefix",
        default=os.environ.get("PEOPLE_API_PREFIX", DEFAULT_PREFIX),
        help=f"where the API is mounted (default: {DEFAULT_PREFIX})",
    )
    args = parser.parse_args(argv)

    # 0.0.0.0, not 127.0.0.1: on WSL a browser on the Windows side cannot always
    # reach a loopback-only listener.
    host = os.environ.get("HOST", "0.0.0.0")
    preferred = int(os.environ.get("PORT", "3001"))
    try:
        app = create_app(args.config, prefix=args.api_prefix)
    except ConfigError as exc:
        raise SystemExit(f"config.yaml is not usable: {exc}") from exc
    port = _find_free_port(host, preferred)
    if port != preferred:
        print(f"Port {preferred} in use, using {port}", flush=True)
    print(f"{app.title} on http://localhost:{port}/", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Local dev server: the People Search API plus the static app.

Run it from the domain Makefile (``make people``), or directly. It serves the
same routes the module mounts inside Nexus, so what works here works there.
"""

from __future__ import annotations

import errno
import os
import socket

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from naas_abi_marketplace.domains.personnel.apps.people.api.routes import router
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import (
    WEB_ROOT,
    ConfigError,
    public_config,
)


def create_app() -> FastAPI:
    config = public_config()
    app = FastAPI(title=config["brand"]["name"])
    app.include_router(router, prefix="/api/personnel-people")
    # One mount: brand files and portraits live under web/assets/, so the paths
    # in config.yaml resolve the same way here and inside Nexus.
    app.mount("/", StaticFiles(directory=WEB_ROOT, html=True), name="web")
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


def main() -> None:
    # 0.0.0.0, not 127.0.0.1: on WSL a browser on the Windows side cannot always
    # reach a loopback-only listener.
    host = os.environ.get("HOST", "0.0.0.0")
    preferred = int(os.environ.get("PORT", "3001"))
    try:
        create_app()
    except ConfigError as exc:
        raise SystemExit(f"config.yaml is not usable: {exc}") from exc
    port = _find_free_port(host, preferred)
    if port != preferred:
        print(f"Port {preferred} in use, using {port}", flush=True)
    print(f"People Search on http://localhost:{port}/", flush=True)
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Local dev server: dataset API + static cockpit UI."""

from __future__ import annotations

import errno
import os
import socket

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from naas_abi_marketplace.domains.personnel.apps.cockpit.api.routes import router
from naas_abi_marketplace.domains.personnel.apps.cockpit.config_loader import (
    public_config,
    public_page_urls,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.data_store import (
    runtime_storage_prefix,
    storage_has_datasets,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.paths import WEB_ROOT


PAGE_URLS = public_page_urls()


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            if _is_spa_path(path):
                response = await super().get_response("index.html", scope)
            else:
                raise
        if (
            path.endswith((".html", ".js", ".css"))
            or not path
            or response.headers.get("content-type", "").startswith("text/html")
        ):
            response.headers["Cache-Control"] = "no-cache"
        return response


def _is_spa_path(path: str) -> bool:
    if not path:
        return True
    parts = path.split("/")
    if parts[0] in PAGE_URLS:
        return True
    if len(parts) >= 2 and parts[1] in PAGE_URLS:
        return True
    return len(parts) == 1 and "." not in parts[0]


def create_app() -> FastAPI:
    if not storage_has_datasets():
        raise SystemExit(
            f"No cockpit datasets in ObjectStorage ({runtime_storage_prefix()}/). "
            "Run: cd domains/personnel && make demo-data"
        )
    app = FastAPI(title=public_config()["brand"]["name"])
    app.include_router(router, prefix="/api/personnel-cockpit")
    app.mount("/", SPAStaticFiles(directory=WEB_ROOT, html=True), name="web")
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
    host = "127.0.0.1"
    preferred = int(os.environ.get("PORT", "3000"))
    port = _find_free_port(host, preferred)
    if port != preferred:
        print(f"Port {preferred} in use, using {port}", flush=True)
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

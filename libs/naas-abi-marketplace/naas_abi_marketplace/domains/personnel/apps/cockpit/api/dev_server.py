#!/usr/bin/env python3
"""Local dev server: dataset API + static cockpit UI."""

from __future__ import annotations

import errno
import json
import os
import socket

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from naas_abi_marketplace.domains.personnel.apps.cockpit.api.routes import router
from naas_abi_marketplace.domains.personnel.apps.cockpit.paths import DATA_ROOT, DEFAULT_ENTITY_ID, WEB_ROOT


def _load_page_ids() -> frozenset[str]:
    manifest_path = DATA_ROOT / "entities" / DEFAULT_ENTITY_ID / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pages = manifest.get("datasets", {}).get("pages", {})
        return frozenset(pages.keys())
    except (OSError, json.JSONDecodeError, AttributeError):
        return frozenset({"workforce", "graph", "processes"})


PAGE_IDS = _load_page_ids()


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            if _is_spa_path(path):
                return await super().get_response("index.html", scope)
            raise


def _is_spa_path(path: str) -> bool:
    if not path:
        return True
    parts = path.split("/")
    if parts[0] in PAGE_IDS:
        return True
    if len(parts) >= 2 and parts[1] in PAGE_IDS:
        return True
    return len(parts) == 1 and "." not in parts[0]


def create_app() -> FastAPI:
    app = FastAPI(title="Personnel Cockpit")
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

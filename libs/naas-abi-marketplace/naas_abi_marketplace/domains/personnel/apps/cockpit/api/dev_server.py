#!/usr/bin/env python3
"""Local dev server: dataset API + static cockpit UI."""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from naas_abi_marketplace.domains.personnel.apps.cockpit.api.routes import router
from naas_abi_marketplace.domains.personnel.apps.cockpit.paths import WEB_ROOT


def create_app() -> FastAPI:
    app = FastAPI(title="Personnel Cockpit")
    app.include_router(router, prefix="/api/personnel-cockpit")
    app.mount("/", StaticFiles(directory=WEB_ROOT, html=True), name="web")
    return app


def main() -> None:
    port = int(os.environ.get("PORT", "3000"))
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()

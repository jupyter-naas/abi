#!/usr/bin/env python3
"""Local server: screener API + static UI."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from naas_abi_marketplace.applications.yahoofinance.apps.screener.api import router

APP_ROOT = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(title="Yahoo Finance Screener")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/yahoofinance/screener")
    app.mount("/", StaticFiles(directory=APP_ROOT, html=True), name="web")
    return app


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

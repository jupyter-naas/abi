"""Mount one People Search instance on a FastAPI application.

An instance is a folder with a ``config.yaml``, a ``web/index.html`` and a
``web/assets/``. Everything else - the routes, the renderers, the stylesheet -
is served from this package, so a second directory costs a config file and a
brand, not a copy of the app.

The shared files are mounted *under the API prefix* rather than at a path of
their own. Nexus proxies ``/api/`` and ``/app-html/`` to the backend and
nothing else, so a new top-level prefix would work in development and 404 in
the product.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from naas_abi_marketplace.domains.personnel.apps.people.api.routes import build_router
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import (
    SHARED_WEB_ROOT,
)
from starlette.staticfiles import StaticFiles

SHARED_WEB_URL = "web"


def shared_web_url(prefix: str) -> str:
    """Where an instance's ``index.html`` finds the shared JS and CSS."""
    return f"{prefix.rstrip('/')}/{SHARED_WEB_URL}"


def mount_people_app(
    app: FastAPI,
    *,
    prefix: str,
    config_path: Path | None = None,
) -> None:
    """Add one instance's API and the renderers its page loads."""
    app.include_router(build_router(config_path), prefix=prefix)
    app.mount(
        shared_web_url(prefix),
        StaticFiles(directory=SHARED_WEB_ROOT),
        name=f"{prefix.strip('/').replace('/', '-')}-shared-web",
    )

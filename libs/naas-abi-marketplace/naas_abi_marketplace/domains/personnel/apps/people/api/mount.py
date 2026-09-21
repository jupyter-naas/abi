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
from naas_abi_marketplace.domains.personnel.apps.people.scripts.graph_view import (
    COCKPIT_PAGES,
)
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

SHARED_WEB_URL = "web"
# The cockpit's page modules, for the profile's graph view. Its scripts are
# loaded as they are rather than copied, so the view stays the cockpit's.
COCKPIT_PAGES_URL = "cockpit-pages"


class RevalidatedStaticFiles(StaticFiles):
    """Static files the browser must check before reusing.

    With no Cache-Control, browsers may reuse a cached ES module for a while
    without asking, so an updated app keeps running old scripts until a hard
    reload. ``no-cache`` still lets them cache: each load is a conditional
    request answered by 304 when nothing changed.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


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
    name = prefix.strip("/").replace("/", "-")
    app.mount(
        shared_web_url(prefix),
        RevalidatedStaticFiles(directory=SHARED_WEB_ROOT),
        name=f"{name}-shared-web",
    )
    app.mount(
        f"{prefix.rstrip('/')}/{COCKPIT_PAGES_URL}",
        RevalidatedStaticFiles(directory=COCKPIT_PAGES),
        name=f"{name}-cockpit-pages",
    )

"""``GET <prefix>/{key}/{name}``: an organization's stored logo, for the URLs the graph holds."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.domains.intelligence.modules.organizations.utils.logo_storage import (
    read_logo,
)

LOGO_URL_PREFIX = "/api/organizations/logos"


def mount_logo_route(
    app: FastAPI,
    get_storage: Callable[[], ObjectStorageService],
    datastore_path: str,
    prefix: str = LOGO_URL_PREFIX,
) -> None:
    def get_logo(key: str, name: str) -> Response:
        found = read_logo(get_storage(), datastore_path, key, name)
        if found is None:
            raise HTTPException(status_code=404, detail="Logo not found")
        content, media_type = found
        # A replaced logo keeps its name: revalidate rather than cache blind.
        return Response(content, media_type=media_type, headers={"Cache-Control": "no-cache"})

    app.add_api_route(
        f"{prefix}/{{key}}/{{name}}",
        get_logo,
        methods=["GET"],
        response_class=Response,
        tags=["organizations"],
    )

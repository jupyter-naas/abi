"""``GET <prefix>/{name}``: a person's stored portrait, for the URLs the graph holds."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.portrait_storage import (
    read_portrait,
)

PORTRAIT_URL_PREFIX = "/api/people/portraits"


def mount_portrait_route(
    app: FastAPI,
    get_storage: Callable[[], ObjectStorageService],
    datastore_path: str,
    prefix: str = PORTRAIT_URL_PREFIX,
) -> None:
    def get_portrait(name: str) -> Response:
        found = read_portrait(get_storage(), datastore_path, name)
        if found is None:
            raise HTTPException(status_code=404, detail="Portrait not found")
        content, media_type = found
        # A re-imported portrait keeps its name: revalidate rather than cache blind.
        return Response(content, media_type=media_type, headers={"Cache-Control": "no-cache"})

    app.add_api_route(
        f"{prefix}/{{name}}",
        get_portrait,
        methods=["GET"],
        response_class=Response,
        tags=["people"],
    )

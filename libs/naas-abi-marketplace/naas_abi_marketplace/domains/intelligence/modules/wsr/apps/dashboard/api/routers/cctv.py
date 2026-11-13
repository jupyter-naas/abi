"""
CCTV router — abi:CCTVStreamingProcess HTTP interface.

Endpoints:
  GET /api/cctv                              — merged camera list (mideast + NYC + London + OWDB)
  GET /api/cctv/snapshot?id=...&kind=image   — a listed camera's current image or
                                               stream (``kind=video``), 4-second TTL
"""

import logging
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from services.cctv import cctv_service
from services.cctv.CCTVService import UnknownCamera

log = logging.getLogger(__name__)
router = APIRouter(tags=["cctv"])


@router.get("/api/cctv")
async def get_cctv() -> JSONResponse:
    cameras = await cctv_service.get_cameras()
    return JSONResponse(
        content=[c.model_dump(by_alias=True) for c in cameras],
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/api/cctv/snapshot")
async def get_cctv_snapshot(
    id: str = Query(..., description="Camera id, from GET /api/cctv"),
    kind: Literal["image", "video"] = Query("image"),
) -> Response:
    try:
        body, ct = await cctv_service.proxy_snapshot(id, kind)
    except UnknownCamera:
        return JSONResponse({"error": "unknown camera"}, status_code=404)
    except Exception as exc:
        log.warning("[cctv/snapshot] proxy failed for camera %s: %s", id, exc)
        return JSONResponse({"error": "camera unavailable"}, status_code=502)
    return Response(
        content=body,
        media_type=ct,
        headers={
            "Cache-Control": "public, max-age=4",
            "X-Content-Type-Options": "nosniff",
        },
    )

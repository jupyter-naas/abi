"""
CCTV router — wsr:CCTVStreamingProcess HTTP interface.

Endpoints:
  GET /api/cctv                   — merged camera list (mideast + NYC + London + OWDB)
  GET /api/cctv/snapshot?url=...  — streaming image/HLS proxy with 4-second TTL
"""

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from services.cctv import cctv_service

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
async def get_cctv_snapshot(url: str = Query(..., description="Source image or HLS URL")) -> Response:
    try:
        body, ct = await cctv_service.proxy_snapshot(url)
        return Response(
            content=body,
            media_type=ct,
            headers={
                "Cache-Control": "public, max-age=4",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as exc:
        log.warning("[cctv/snapshot] proxy failed for %s: %s", url, exc)
        return JSONResponse({"error": str(exc)}, status_code=502)

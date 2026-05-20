"""
Webcams router — OpenWebcamDB list + stream URL resolution.

Endpoints:
  GET /api/webcams              — paginated OpenWebcamDB camera list (cached 1 h)
  GET /api/webcams/stream?slug= — resolve stream URL for a specific slug (cached 30 min)
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from services.webcams import webcam_service

router = APIRouter(tags=["webcams"])


@router.get("/api/webcams")
async def get_webcams() -> JSONResponse:
    if not webcam_service.is_configured:
        raise HTTPException(status_code=503, detail="OPENWEBCAMDB_API_KEY not configured")
    data = await webcam_service.get_webcams()
    return JSONResponse(
        content=[c.model_dump(by_alias=True) for c in data],
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/webcams/stream")
async def get_webcam_stream(slug: str = Query(..., description="OpenWebcamDB webcam slug")) -> JSONResponse:
    if not webcam_service.is_configured:
        raise HTTPException(status_code=503, detail="OPENWEBCAMDB_API_KEY not configured")
    if not slug:
        raise HTTPException(status_code=400, detail="missing slug")
    try:
        result = await webcam_service.get_stream_url(slug)
        return JSONResponse(content=result.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

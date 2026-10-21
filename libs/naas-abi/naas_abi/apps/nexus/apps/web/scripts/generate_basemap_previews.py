#!/usr/bin/env python3
"""Stitch map tiles into basemap picker preview PNGs (no data layers)."""

from __future__ import annotations

import io
import math
import urllib.request
from pathlib import Path

from PIL import Image

# Same ids as maps-basemaps.ts
BASEMAPS: dict[str, str] = {
    "openstreetmap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "esri-imagery": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "opentopomap": "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
}

# Central Europe — readable street / terrain / imagery at mid zoom.
LAT = 46.8
LNG = 8.2
ZOOM = 6
GRID = 2  # 2×2 tiles
OUT_SIZE = 104
USER_AGENT = "ForvisMazars-BobMaps-BasemapPreview/1.0 (+local dev asset generator)"


def lat_lng_to_tile(lat: float, lng: float, zoom: int) -> tuple[int, int]:
    n = 2**zoom
    x = int((lng + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def fetch_tile(url: str) -> Image.Image:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return Image.open(io.BytesIO(response.read())).convert("RGB")


def preview_for(basemap_id: str, template: str) -> Image.Image:
    x0, y0 = lat_lng_to_tile(LAT, LNG, ZOOM)
    tile_px = 256
    canvas = Image.new("RGB", (tile_px * GRID, tile_px * GRID))
    for row in range(GRID):
        for col in range(GRID):
            x, y = x0 + col, y0 + row
            url = template.format(z=ZOOM, x=x, y=y)
            tile = fetch_tile(url)
            canvas.paste(tile, (col * tile_px, row * tile_px))
    return canvas.resize((OUT_SIZE, OUT_SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "public" / "maps" / "basemaps"
    out_dir.mkdir(parents=True, exist_ok=True)
    for basemap_id, template in BASEMAPS.items():
        path = out_dir / f"{basemap_id}.png"
        print(f"Writing {path}…")
        preview_for(basemap_id, template).save(path, format="PNG", optimize=True)
    print("Done.")


if __name__ == "__main__":
    main()

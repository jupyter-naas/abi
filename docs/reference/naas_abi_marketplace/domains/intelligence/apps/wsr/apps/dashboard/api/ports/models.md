# API DTO Models (WSR)

## What it is
JSON-serializable Pydantic Data Transfer Objects (DTOs) representing WSR domain types for the API layer. These mirror frontend TypeScript types, preserving field names and units across the API boundary (e.g., coordinates in decimal degrees, time in Unix epoch ms).

## Public API
- `class FlightState(BaseModel)`
  - Aircraft position report DTO.
  - Fields: `icao24`, `callsign`, `lat`, `lon`, `altitude` (metres ASL), `velocity` (m/s), `heading` (degrees true), `on_ground` (alias: `onGround`, default `False`), `is_military` (alias: `isMilitary`, default `None`).

- `class SatelliteRecord(BaseModel)`
  - Satellite TLE record DTO.
  - Fields: `name`, `line1`, `line2`.

- `class EarthquakeFeature(BaseModel)`
  - Earthquake event DTO.
  - Fields: `id`, `mag`, `place`, `lat`, `lon`, `depth` (km below surface), `time` (Unix epoch ms).

- `SeverityLevel = Literal["breaking", "alert", "update"]`
  - Allowed severity values for `NewsItem`.

- `class NewsItem(BaseModel)`
  - News article DTO.
  - Fields: `id`, `title`, `source`, `url`, `pub_date` (alias: `pubDate`, Unix epoch ms), `severity` (`SeverityLevel`).

- `ConflictType = Literal["strike", "base", "nuclear", "naval", "zone", "capital"]`
  - Allowed conflict site types.

- `ThreatSeverity = Literal["critical", "high", "medium"]`
  - Allowed threat severity values.

- `class ConflictEvent(BaseModel)`
  - Conflict site record DTO.
  - Fields: `id`, `name`, `lat`, `lon`, `type` (`ConflictType`), `country`, `description`, `severity` (`ThreatSeverity`).

- `StreamType = Literal["hls", "mp4", "youtube"]`
  - Allowed stream types for CCTV camera records.

- `CameraSource = Literal["nyc", "london", "openwebcamdb", "mideast"]`
  - Allowed source values for CCTV camera records.

- `class CCTVCamera(BaseModel)`
  - CCTV camera unit DTO.
  - Fields: `id`, `name`, `lat`, `lon`, `city`, `country` (optional), `image_url` (alias: `imageUrl`, default `""`), `video_url` (alias: `videoUrl`, default `""`), `type` (`StreamType`), `source` (`CameraSource`), `slug` (optional), `active` (default `True`).

- `class StreamResult(BaseModel)`
  - Webcam stream resolver response DTO (not tied to an ontology class).
  - Fields: `url`, `type` (always `"youtube"` by default).

## Configuration/Dependencies
- Depends on:
  - `pydantic.BaseModel`, `pydantic.Field`
  - `typing.Literal`
- Models with `model_config = {"populate_by_name": True}`:
  - `FlightState`, `NewsItem`, `CCTVCamera`
  - Allows populating fields by either Python attribute name or JSON alias (e.g., `on_ground` or `onGround`).

## Usage
```python
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.ports.models import (
    FlightState, NewsItem, CCTVCamera
)

fs = FlightState(
    icao24="abc123",
    callsign="TEST01",
    lat=48.8566,
    lon=2.3522,
    altitude=1200.0,
    velocity=210.0,
    heading=90.0,
    onGround=False,      # alias supported
    isMilitary=None,     # alias supported
)

print(fs.model_dump(by_alias=True))  # emits onGround/isMilitary keys

news = NewsItem(
    id="n1",
    title="Example",
    source="wire",
    url="https://example.com",
    pubDate=1720000000000,  # alias supported
    severity="breaking",
)

cam = CCTVCamera(
    id="c1",
    name="Cam",
    lat=51.5,
    lon=-0.1,
    city="London",
    type="youtube",
    source="london",
    imageUrl="https://example.com/img.jpg",  # alias supported
    videoUrl="https://youtube.com/watch?v=...",
)
```

## Caveats
- `Literal[...]`-typed fields (`severity`, conflict `type`, `severity`, camera `type`, `source`) only accept the enumerated string values.
- Alias fields (`onGround`, `isMilitary`, `pubDate`, `imageUrl`, `videoUrl`) require `by_alias=True` when dumping if you need JSON keys to match the API schema.

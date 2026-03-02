"""
API Data Transfer Objects — JSON-serializable view of WSR domain types.

These are the Python mirror of the TypeScript types in frontend/src/lib/types.ts.
Field names and units are intentionally identical on both sides of the API boundary:
  - coordinates: decimal degrees WGS84
  - altitude: metres above sea level
  - velocity: m/s
  - heading: degrees true (0–360)
  - time: Unix epoch milliseconds (int)

Ontology mapping (wsr.ttl → make generate → ports/domain.py):
  FlightState       → wsr:AircraftPositionReport    rdfs:subClassOf wsr:InformationContentEntity
  SatelliteRecord   → wsr:TLERecord                 rdfs:subClassOf wsr:InformationContentEntity
  EarthquakeFeature → wsr:EarthquakeEventRecord      rdfs:subClassOf wsr:InformationContentEntity
  NewsItem          → wsr:NewsArticle                rdfs:subClassOf wsr:InformationContentEntity
  ConflictEvent     → wsr:ConflictSiteRecord         rdfs:subClassOf wsr:InformationContentEntity
  CCTVCamera        → wsr:CCTVCameraUnit             rdfs:subClassOf wsr:GroundSensorStation

Each class here is a lightweight Pydantic DTO optimised for JSON.
The authoritative domain model (RDFEntity subclasses with rdf() serialisation)
lives in ports/domain.py, which is auto-generated — run `make generate` to
regenerate it from ontology/wsr.ttl.

Hexagonal flow:
  wsr.ttl  ──[make generate]──▶  ports/domain.py   (domain model / RDF layer)
                                         │
                               ports/models.py      (API DTO layer, this file)
                                         │
                               services/{domain}/   (orchestration layer)
                                         │
                               services/{domain}/adapters/  (infrastructure layer)
                                         │
                               routers/*.py         (HTTP delivery layer)
"""

from typing import Literal

from pydantic import BaseModel, Field


# ─── wsr:AircraftPositionReport  (GDC — Information Content Entity) ──────────
# domain.py: AircraftPositionReport  ·  wsr:hasICAO24 · wsr:hasCallsign
#            wsr:hasLat · wsr:hasLon · wsr:hasAltitude · wsr:hasVelocity
#            wsr:hasHeading · wsr:isOnGround · wsr:isMilitary

class FlightState(BaseModel):
    icao24: str
    callsign: str
    lat: float
    lon: float
    altitude: float = Field(description="metres ASL")
    velocity: float = Field(description="m/s")
    heading: float = Field(description="degrees true")
    on_ground: bool = Field(alias="onGround", default=False)
    is_military: bool | None = Field(alias="isMilitary", default=None)

    model_config = {"populate_by_name": True}


# ─── wsr:TLERecord  (GDC — Information Content Entity) ───────────────────────
# domain.py: TLERecord  ·  wsr:hasTLELine1 · wsr:hasTLELine2

class SatelliteRecord(BaseModel):
    name: str
    line1: str
    line2: str


# ─── wsr:EarthquakeEventRecord  (GDC — Information Content Entity) ────────────
# domain.py: EarthquakeEventRecord  ·  wsr:hasMagnitude · wsr:hasPlace
#            wsr:hasLat · wsr:hasLon · wsr:hasDepth · wsr:hasEventTime

class EarthquakeFeature(BaseModel):
    id: str
    mag: float
    place: str
    lat: float
    lon: float
    depth: float = Field(description="km below surface")
    time: int    = Field(description="Unix epoch ms")


# ─── wsr:NewsArticle  (GDC — Information Content Entity) ─────────────────────
# domain.py: NewsArticle  ·  wsr:hasTitle · wsr:hasNewsSource
#            wsr:hasSourceURL · wsr:hasPubDate · wsr:hasSeverityClass

SeverityLevel = Literal["breaking", "alert", "update"]

class NewsItem(BaseModel):
    id: str
    title: str
    source: str
    url: str
    pub_date: int = Field(alias="pubDate", description="Unix epoch ms")
    severity: SeverityLevel

    model_config = {"populate_by_name": True}


# ─── wsr:ConflictSiteRecord  (GDC — Information Content Entity) ───────────────
# domain.py: ConflictSiteRecord  ·  wsr:hasConflictSiteName · wsr:hasSiteType
#            wsr:hasLat · wsr:hasLon · wsr:hasSiteCountry
#            wsr:hasSiteDescription · wsr:hasThreatSeverity

ConflictType     = Literal["strike", "base", "nuclear", "naval", "zone", "capital"]
ThreatSeverity   = Literal["critical", "high", "medium"]

class ConflictEvent(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    type: ConflictType
    country: str
    description: str
    severity: ThreatSeverity


# ─── wsr:CCTVCameraUnit  (Material Entity — GroundSensorStation) ──────────────
# domain.py: CCTVCameraUnit  ·  wsr:hasCameraName · wsr:hasCity · wsr:hasCountry
#            wsr:hasLat · wsr:hasLon · wsr:hasImageURL · wsr:hasVideoURL
#            wsr:hasStreamType · wsr:hasCameraSource · wsr:hasSlug

StreamType   = Literal["hls", "mp4", "youtube"]
CameraSource = Literal["nyc", "london", "openwebcamdb", "mideast"]

class CCTVCamera(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    city: str
    country: str | None = None
    image_url: str = Field(alias="imageUrl", default="")
    video_url: str = Field(alias="videoUrl", default="")
    type: StreamType
    source: CameraSource
    slug: str | None = None
    active: bool = True

    model_config = {"populate_by_name": True}


# ─── Webcam stream resolver response  (no direct ontology class) ─────────────

class StreamResult(BaseModel):
    url: str
    type: Literal["youtube"] = "youtube"

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
  FlightState       → abi:AircraftPositionReport    rdfs:subClassOf abi:InformationContentEntity
  SatelliteRecord   → abi:TLERecord                 rdfs:subClassOf abi:InformationContentEntity
  EarthquakeFeature → abi:EarthquakeEventRecord      rdfs:subClassOf abi:InformationContentEntity
  NewsItem          → abi:NewsArticle                rdfs:subClassOf abi:InformationContentEntity
  ConflictEvent     → abi:ConflictSiteRecord         rdfs:subClassOf abi:InformationContentEntity
  CCTVCamera        → abi:CCTVCameraUnit             rdfs:subClassOf abi:GroundSensorStation

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

# ─── abi:AircraftPositionReport  (GDC — Information Content Entity) ──────────
# domain.py: AircraftPositionReport  ·  abi:hasICAO24 · abi:hasCallsign
#            abi:hasLat · abi:hasLon · abi:hasAltitude · abi:hasVelocity
#            abi:hasHeading · abi:isOnGround · abi:isMilitary

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


# ─── abi:TLERecord  (GDC — Information Content Entity) ───────────────────────
# domain.py: TLERecord  ·  abi:hasTLELine1 · abi:hasTLELine2

class SatelliteRecord(BaseModel):
    name: str
    line1: str
    line2: str


# ─── abi:EarthquakeEventRecord  (GDC — Information Content Entity) ────────────
# domain.py: EarthquakeEventRecord  ·  abi:hasMagnitude · abi:hasPlace
#            abi:hasLat · abi:hasLon · abi:hasDepth · abi:hasEventTime

class EarthquakeFeature(BaseModel):
    id: str
    mag: float
    place: str
    lat: float
    lon: float
    depth: float = Field(description="km below surface")
    time: int    = Field(description="Unix epoch ms")


# ─── abi:NewsArticle  (GDC — Information Content Entity) ─────────────────────
# domain.py: NewsArticle  ·  abi:hasTitle · abi:hasNewsSource
#            abi:hasSourceURL · abi:hasPubDate · abi:hasSeverityClass

SeverityLevel = Literal["breaking", "alert", "update"]

class NewsItem(BaseModel):
    id: str
    title: str
    source: str
    url: str
    pub_date: int = Field(alias="pubDate", description="Unix epoch ms")
    severity: SeverityLevel

    model_config = {"populate_by_name": True}


# ─── abi:ConflictSiteRecord  (GDC — Information Content Entity) ───────────────
# domain.py: ConflictSiteRecord  ·  abi:hasConflictSiteName · abi:hasSiteType
#            abi:hasLat · abi:hasLon · abi:hasSiteCountry
#            abi:hasSiteDescription · abi:hasThreatSeverity

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


# ─── abi:CCTVCameraUnit  (Material Entity — GroundSensorStation) ──────────────
# domain.py: CCTVCameraUnit  ·  abi:hasCameraName · abi:hasCity · abi:hasCountry
#            abi:hasLat · abi:hasLon · abi:hasImageURL · abi:hasVideoURL
#            abi:hasStreamType · abi:hasCameraSource · abi:hasSlug

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

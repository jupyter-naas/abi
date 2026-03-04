# WSR — World Situation Room

Real-time geospatial intelligence platform. Fuses live satellite orbits, commercial and military flight data, seismic activity, CCTV streams, and conflict-zone intelligence into a single 3D globe — all from open-source feeds.

---

## What it does

| Layer | Source | Refresh |
|---|---|---|
| Satellites (all active) | CelesTrak TLE | 1 h |
| Commercial flights | OpenSky Network / airplanes.live | 30 s |
| Military flights | ADSB.lol → airplanes.live fallback | 60 s |
| Theater aircraft (Middle East) | airplanes.live (3-region fan-out) | 45 s |
| Earthquakes M≥1.0 | USGS GeoJSON feed | 5 min |
| CCTV — New York | 511NY.org | 5 min |
| CCTV — London (~900 cameras) | TfL JamCam API | 5 min |
| CCTV — Middle East theater | Curated static dataset | static |
| CCTV — Global webcams | OpenWebcamDB (API key required) | 5 min |
| Conflict zones | OSINT-sourced static dataset (20 sites) | static |
| Intel feed | BBC / Al Jazeera / Reuters RSS | 3 min |

Visual modes: default, CRT, night-vision (NVG), thermal, bloom. Space-to-dive camera, GeoSearch, detection mode overlays, scrolling intel ticker, live CCTV panel.

---

## Architecture

```
Browser
  └── GlobeEngine (TypeScript)
        ├── IGlobeLayerPort adapters   — Cesium rendering (one per BFO process)
        └── IDataSourcePort adapters   — fetch from FastAPI (one per ICE type)

FastAPI backend (port 8000)
  └── routers/           — thin HTTP delivery (one per BFO process type)
        └── services/    — domain orchestration (fan-out, merge, fallback)
              └── adapters/  — one per external data source

Ontology
  └── ontology/wsr.ttl   — single source of truth for all domain concepts
        ↓ make generate
  └── backend/ports/domain.py   — auto-generated Pydantic + RDF domain types
        ↓ hand-mapped
  └── backend/ports/models.py   — API DTOs (JSON-optimised)
```

The design follows a hexagonal (ports & adapters) pattern grounded in **BFO** (Basic Formal Ontology). Every router maps 1:1 to a BFO process class defined in `ontology/wsr.ttl`.

---

## Project layout

```
wsr/
├── AGENTS.md                    # contributor guide — read before adding anything
├── Makefile                     # dev launcher + code generator
├── README.md
├── ontology/
│   ├── wsr.ttl                  # BFO-grounded OWL ontology (@prefix wsr:)
│   └── wsr-instances.ttl        # named individuals
├── backend/                     # Python 3.11+ / FastAPI
│   ├── main.py                  # app + middleware + router registration
│   ├── settings.py              # pydantic-settings — all env vars here
│   ├── pyproject.toml
│   ├── .env.example
│   ├── core/
│   │   ├── cache.py             # generic TTLCache[T]
│   │   └── http_client.py       # shared async httpx client
│   ├── ports/
│   │   ├── domain.py            # AUTO-GENERATED — run `make generate`
│   │   └── models.py            # hand-written API DTOs (mirrors TypeScript types)
│   ├── services/
│   │   ├── cctv/
│   │   │   ├── CCTVPort.py      # ICCTVAdapter, ICCTVService interfaces
│   │   │   ├── CCTVService.py   # fan-out to adapters, snapshot proxy
│   │   │   ├── __init__.py      # cctv_service singleton
│   │   │   └── adapters/
│   │   │       ├── london.py    # TfL JamCam
│   │   │       ├── nyc.py       # 511NY.org
│   │   │       └── mideast.py   # static theater cameras
│   │   ├── flights/
│   │   │   ├── FlightsPort.py
│   │   │   ├── FlightsService.py
│   │   │   ├── __init__.py
│   │   │   └── adapters/
│   │   │       ├── opensky.py   # OAuth2 → basic auth → airplanes.live fallback
│   │   │       ├── adsb_lol.py  # military: ADSB.lol → airplanes.live fallback
│   │   │       └── airplanes_live.py
│   │   ├── satellites/          # CelesTrak TLE
│   │   ├── earthquakes/         # USGS GeoJSON
│   │   ├── news/                # BBC / Al Jazeera / Reuters RSS
│   │   ├── conflict/            # static OSINT dataset
│   │   └── webcams/             # OpenWebcamDB
│   └── routers/
│       ├── flights.py
│       ├── satellites.py
│       ├── earthquakes.py
│       ├── news.py
│       ├── conflict.py
│       ├── cctv.py
│       └── webcams.py
└── frontend/                    # Next.js 14 + CesiumJS
    └── src/
        ├── app/
        │   ├── layout.tsx       # browser title, metadata
        │   └── page.tsx
        ├── components/
        │   ├── WSR.tsx          # root globe component — engine init + event wiring
        │   └── ui/
        │       ├── StatusBar.tsx       # top navbar + GeoSearch
        │       ├── DataLayerPanel.tsx  # left panel — layer toggles + live counts
        │       ├── IntelPanel.tsx      # left panel — news + conflict list
        │       ├── IntelTicker.tsx     # full-width scrolling news ribbon
        │       ├── CCTVPanel.tsx       # live CCTV feed viewer
        │       └── GeoSearch.tsx       # Nominatim place search
        └── lib/
            ├── ontology.ts      # TypeScript BFO process type bindings
            ├── types.ts         # TypeScript mirror of backend/ports/models.py
            ├── shaders.ts       # post-processing shader definitions
            └── globe/
                ├── GlobeEngine.ts       # hexagonal engine core
                ├── GlobeLayerBase.ts    # abstract base for layer adapters
                ├── ports/
                │   ├── IGlobeLayerPort.ts
                │   ├── IDataSourcePort.ts
                │   └── ICesiumContextPort.ts
                └── adapters/
                    ├── layers/          # one adapter per rendered layer
                    │   ├── FlightLayerAdapter.ts
                    │   ├── MilitaryLayerAdapter.ts
                    │   ├── TheaterAircraftAdapter.ts
                    │   ├── CCTVLayerAdapter.ts
                    │   ├── EarthquakeLayerAdapter.ts
                    │   ├── ConflictZoneAdapter.ts
                    │   ├── BorderLayerAdapter.ts
                    │   └── CityLabelAdapter.ts
                    └── data/            # one adapter per backend endpoint
                        ├── FlightDataSource.ts
                        └── SpatialDataSources.ts
```

---

## Requirements

| Tool | Version |
|---|---|
| Node.js | ≥ 20 |
| Python | ≥ 3.11 |
| pip packages | `fastapi uvicorn[standard] httpx pydantic pydantic-settings rdflib` |

---

## Setup

**Backend**

```bash
cd backend
pip install fastapi "uvicorn[standard]" httpx pydantic pydantic-settings rdflib
cp .env.example .env   # fill in API keys (all optional, see table below)
```

**Frontend**

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_CESIUM_TOKEN=          # free at ion.cesium.com — enables terrain + imagery
```

---

## Running

```bash
# From wsr/ — starts both services in the background
make dev

# Tail logs for both
make logs

# Stop both
make stop

# Foreground (useful for debugging one service at a time)
make api    # FastAPI only  — http://localhost:8000
make ui     # Next.js only  — http://localhost:3000

# Regenerate backend/ports/domain.py from ontology/wsr.ttl
make generate
```

FastAPI interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API endpoints

| Method | Path | Service | Description |
|---|---|---|---|
| GET | `/api/flights` | FlightsService | Civil aviation position reports |
| GET | `/api/military` | FlightsService | Military aircraft (ADSB.lol) |
| GET | `/api/mideast-aircraft` | FlightsService | Theater aircraft (airplanes.live) |
| GET | `/api/satellites` | SatellitesService | TLE records (CelesTrak) |
| GET | `/api/earthquakes` | EarthquakesService | M≥1.0 seismic events, past 24 h |
| GET | `/api/news` | NewsService | RSS aggregation (BBC / AJ / Reuters) |
| GET | `/api/conflict-events` | ConflictService | Static OSINT conflict site list |
| GET | `/api/cctv` | CCTVService | Merged camera list (all sources) |
| GET | `/api/cctv/snapshot?url=` | CCTVService | Server-side image/HLS proxy |
| GET | `/api/webcams` | WebcamsService | OpenWebcamDB camera list |
| GET | `/api/webcams/stream?slug=` | WebcamsService | Stream URL resolver |
| GET | `/health` | — | Health check |

---

## Environment variables

**Backend** (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `OPENSKY_CLIENT_ID` | No | OAuth2 client ID — new OpenSky accounts (post-March 2025) |
| `OPENSKY_CLIENT_SECRET` | No | OAuth2 client secret |
| `OPENSKY_USERNAME` | No | Legacy basic-auth — pre-March 2025 accounts |
| `OPENSKY_PASSWORD` | No | Legacy basic-auth password |
| `TFL_APP_KEY` | No | TfL API key — raises JamCam rate limit from 60 to 500 req/min |
| `OPENWEBCAMDB_API_KEY` | No | Enables `/api/webcams` and OWDB cameras in `/api/cctv` |
| `ALLOWED_ORIGINS` | No | JSON array of allowed CORS origins, default `["*"]` |

Without any API keys the backend still works: flights fall back to `airplanes.live`, London CCTV works anonymously (with lower rate limits), and OpenWebcamDB is simply disabled.

**Frontend** (`frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | FastAPI base URL, e.g. `http://localhost:8000` |
| `NEXT_PUBLIC_CESIUM_TOKEN` | No | Enables Cesium Ion terrain and imagery |
| `NEXT_PUBLIC_GOOGLE_MAPS_KEY` | No | Enables Google Photorealistic 3D Tiles |

---

## Ontology

All domain concepts are declared in `ontology/wsr.ttl` using the `wsr:` namespace (`http://ontology.naas.ai/wsr/`) and grounded in [BFO 2020](https://basic-formal-ontology.org/).

| BFO bucket | WSR classes |
|---|---|
| Site (BFO_0000029) | `GeographicSite`, `ConflictZone`, `NuclearFacilitySite`, `MilitaryBaseSite`, `AirspaceRegion`, `OrbitalShell` |
| Material Entity (BFO_0000040) | `Satellite`, `Aircraft`, `MilitaryAircraft`, `CivilAircraft`, `NavalVessel`, `CCTVCameraUnit`, `SeismographStation`, `DataSourceEndpoint` |
| GDC / ICE (BFO_0000031) | `TLERecord`, `AircraftPositionReport`, `EarthquakeEventRecord`, `NewsArticle`, `ConflictSiteRecord`, `VideoStream`, `RSSFeed` |
| Quality (BFO_0000019) | `GeographicCoordinate`, `AltitudeQuality`, `EarthquakeMagnitude`, `ThreatSeverityLevel`, `CacheDuration` |
| Role (BFO_0000023) | `SurveillanceSourceRole`, `IntelligenceSourceRole`, `TrackingTargetRole`, `TheaterActorRole` |
| Disposition (BFO_0000016) | `StreamingDisposition`, `ADSBTransponderDisposition`, `OrbitalPropagationDisposition` |
| Process (BFO_0000015) | `FlightTrackingProcess`, `SatelliteTrackingProcess`, `EarthquakeMonitoringProcess`, `CCTVStreamingProcess`, `NewsAggregationProcess`, `GlobeRenderingProcess`, `ThreatAssessmentProcess` |

Running `make generate` converts the TTL into `backend/ports/domain.py` — Pydantic model classes with a `.rdf()` method for serialising instances back to RDF triples. The hand-written `backend/ports/models.py` provides clean API DTOs aligned to the same ontology.

---

## Contributing

See **[AGENTS.md](./AGENTS.md)** for the full contributor and agent guide. It covers:

- The mandatory ontology-first development order
- End-to-end walkthrough for adding a new data layer (backend + frontend)
- How to add a new adapter to an existing domain
- Coding conventions (naming, units, caching, error handling)
- A complete checklist before submitting any change
- What not to do — and the exact bugs each anti-pattern caused

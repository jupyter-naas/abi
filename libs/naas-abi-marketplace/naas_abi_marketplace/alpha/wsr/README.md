# WSR — World Situation Room

Real-time geospatial intelligence platform. Fuses live satellite orbits, commercial and military flight data, seismic activity, CCTV streams, and conflict-zone intelligence into a single 3D globe — all from open-source feeds.

---

## What it does

| Layer | Source | Refresh |
|---|---|---|
| Satellites (all active) | CelesTrak TLE | 1 h |
| Commercial flights | OpenSky Network | 30 s |
| Military flights | ADSB.lol `/v2/mil` | 60 s |
| Theater aircraft (Middle East) | airplanes.live (3-region fan-out) | 45 s |
| Earthquakes M≥1.0 | USGS GeoJSON feed | 5 min |
| CCTV — New York | 511NY.org | 5 min |
| CCTV — London | TfL JamCam | 5 min |
| CCTV — Middle East theater | Curated (Jerusalem, Beirut, Dubai) | static |
| Conflict zones | OSINT-sourced static dataset (20 sites) | static |
| News | BBC / Al Jazeera / Reuters RSS | 3 min |

Visual modes: default, CRT, night-vision (NVG), thermal, bloom. Satellite orbit tracking, detection mode overlays, city/landmark navigation, GeoSearch.

---

## Architecture

```
Browser
  └── GlobeEngine (TS)
        ├── IGlobeLayerPort adapters   → Cesium rendering (borders, cities, flights, …)
        └── IDataSourcePort adapters   → fetch from FastAPI

FastAPI (port 8000)
  └── Routers (1:1 BFO process type)
        └── Secondary adapters (OpenSky, ADSB.lol, airplanes.live, CelesTrak, USGS, …)
```

The design mirrors a hexagonal (ports & adapters) pattern grounded in **BFO** (Basic Formal Ontology). Formal types live in `ontology/wsr.ttl`; their TypeScript mirror is `frontend/src/lib/ontology.ts`; their Python mirror is `backend/ports/models.py`.

---

## Project layout

```
wsr/
├── Makefile                  # dev launcher
├── ontology/
│   ├── wsr.ttl               # BFO class hierarchy  (@prefix wsr:)
│   └── wsr-instances.ttl     # named individuals
├── backend/                  # Python FastAPI service
│   ├── main.py
│   ├── settings.py
│   ├── pyproject.toml
│   ├── core/
│   │   ├── cache.py          # generic TTLCache[T]
│   │   └── http_client.py    # shared httpx.AsyncClient
│   ├── ports/
│   │   └── models.py         # Pydantic canonical types
│   ├── adapters/             # secondary adapters (one per data source)
│   └── routers/              # HTTP layer (one per BFO process type)
└── frontend/                 # Next.js + CesiumJS
    └── src/
        ├── app/page.tsx
        ├── components/
        │   ├── WSR.tsx        # root globe component
        │   └── ui/
        │       ├── CCTVPanel.tsx
        │       └── GeoSearch.tsx
        └── lib/
            ├── ontology.ts    # TypeScript BFO bindings
            ├── types.ts
            └── globe/
                ├── GlobeEngine.ts
                ├── ports/
                └── adapters/
                    ├── layers/
                    └── data/
```

---

## Requirements

| Tool | Version |
|---|---|
| Node.js | ≥ 20 |
| Python | ≥ 3.11 |
| pip packages | `fastapi uvicorn httpx pydantic pydantic-settings` |

---

## Setup

**Backend**

```bash
cd backend
pip install fastapi "uvicorn[standard]" httpx pydantic pydantic-settings
cp .env.example .env   # add OpenSky / OpenWebcamDB keys if you have them
```

**Frontend**

```bash
cd frontend
npm install
cp .env.local.example .env.local   # or edit .env.local directly
```

`.env.local` minimum:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_CESIUM_TOKEN=          # free at ion.cesium.com (enables terrain)
```

---

## Running

```bash
# From wsr/ root — starts both services in the background
make dev

# Tail logs for both
make logs

# Stop both
make stop

# Foreground (useful for debugging a single service)
make api    # FastAPI only  — http://localhost:8000
make ui     # Next.js only  — http://localhost:3000
```

FastAPI interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/flights` | Civil aviation (OpenSky) |
| GET | `/api/military` | Military aircraft (ADSB.lol) |
| GET | `/api/mideast-aircraft` | Theater aircraft (airplanes.live) |
| GET | `/api/satellites` | TLE records (CelesTrak) |
| GET | `/api/earthquakes` | M≥1.0 events, past 24 h (USGS) |
| GET | `/api/news` | Region-filtered RSS (BBC / AJ / Reuters) |
| GET | `/api/conflict-events` | Static OSINT conflict site list |
| GET | `/api/cctv` | Merged camera list (NYC + London + theater) |
| GET | `/api/cctv/snapshot?url=` | Server-side image/HLS proxy |
| GET | `/api/webcams` | OpenWebcamDB list (requires API key) |
| GET | `/api/webcams/stream?slug=` | Stream URL resolver |
| GET | `/health` | Health check |

---

## Environment variables

**Backend** (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `OPENSKY_USERNAME` | No | Higher rate limits on OpenSky |
| `OPENSKY_PASSWORD` | No | |
| `OPENWEBCAMDB_API_KEY` | No | Enables global webcam layer |
| `ALLOWED_ORIGINS` | No | JSON array, default `["http://localhost:3000"]` |

**Frontend** (`frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | FastAPI base URL |
| `NEXT_PUBLIC_CESIUM_TOKEN` | No | Enables Cesium Ion terrain / imagery |
| `NEXT_PUBLIC_GOOGLE_MAPS_KEY` | No | Enables Google Photorealistic 3D Tiles |

---

## Ontology

All domain concepts are grounded in [BFO 2020](https://basic-formal-ontology.org/) using the `wsr:` namespace (`http://ontology.naas.ai/wsr/`).

| BFO bucket | WSR classes |
|---|---|
| Site | `wsr:GeographicSite`, `wsr:ConflictZone`, `wsr:AirspaceRegion` |
| Material Entity | `wsr:Satellite`, `wsr:Aircraft`, `wsr:CCTVCameraUnit` |
| GDC / ICE | `wsr:TLERecord`, `wsr:AircraftPositionReport`, `wsr:EarthquakeEventRecord`, `wsr:NewsArticle` |
| Quality | `wsr:GeographicCoordinate`, `wsr:ThreatSeverityLevel` |
| Role | `wsr:SurveillanceSourceRole`, `wsr:DataProviderRole` |
| Disposition | `wsr:StreamingDisposition`, `wsr:ADSBTransponderDisposition` |
| Process | `wsr:FlightTrackingProcess`, `wsr:SatelliteTrackingProcess`, `wsr:EarthquakeMonitoringProcess`, … |

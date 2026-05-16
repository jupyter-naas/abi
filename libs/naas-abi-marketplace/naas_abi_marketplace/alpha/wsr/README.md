# WSR — World Situation Room

Real-time geospatial intelligence platform. Fuses live satellite orbits, commercial and military flight data, seismic activity, CCTV streams, and conflict-zone intelligence into a single 3D globe — all from open-source feeds.

Part of the [ABI Marketplace](https://github.com/jupyter-naas/abi) (`naas_abi_marketplace.alpha.wsr`).

---

## Data layers

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
| Intel feed | BBC / Al Jazeera RSS | 3 min |

Visual modes: default, CRT, night-vision (NVG), thermal, bloom. Space-to-dive camera, GeoSearch, detection mode overlays, scrolling intel ticker, live CCTV panel.

---

## Module layout

```
wsr/
├── __init__.py              # ABI module registration (ABIModule + Configuration)
├── README.md
├── AGENTS.md                # contributor guide — read before changing anything
├── ARCHITECTURE.md          # system design and BFO grounding
├── TODO.md                  # backlog
├── agents/
│   └── WSRAgent.py          # ABI chat agent for situational awareness queries
├── apps/
│   ├── Makefile             # dev launcher: make dev / stop / logs / api / ui
│   ├── api/                 # Python 3.11+ / FastAPI — geospatial data service
│   │   ├── main.py
│   │   ├── settings.py
│   │   ├── pyproject.toml
│   │   ├── .env.example
│   │   ├── core/            # TTLCache, shared httpx client
│   │   ├── ports/           # domain.py (auto-generated) + models.py (DTOs)
│   │   ├── services/        # cctv, flights, satellites, earthquakes, news, conflict, webcams
│   │   └── routers/
│   └── web/                 # Next.js 16 + CesiumJS — 3D globe frontend
│       ├── src/
│       │   ├── app/         # login gate (page.tsx) + layout
│       │   ├── components/  # WSR.tsx (root), LoginPage.tsx, ui/
│       │   └── lib/         # auth.ts, ontology.ts, types.ts, globe/
│       ├── .env.local        # optional: NEXT_PUBLIC_CESIUM_TOKEN
│       └── next.config.ts   # proxies /api/* to apps/api (no CORS, no env var needed)
└── ontology/
    ├── wsr.ttl              # BFO-grounded OWL ontology
    └── wsr-instances.ttl    # named individuals
```

---

## Requirements

| Tool | Version |
|---|---|
| Python | ≥ 3.11 |
| Node.js | ≥ 20 |
| uv | any recent |
| npm | ≥ 9 |

---

## Setup

```bash
# API dependencies
cd apps/api
uv pip install "fastapi>=0.115" "uvicorn[standard]>=0.30" "httpx>=0.27" \
               "pydantic>=2.7" "pydantic-settings>=2.3" "python-dotenv>=1.0"

# Frontend dependencies
cd apps/web
npm install
```

---

## Running

```bash
# From apps/ — starts both services in the background
cd apps
make dev

# Tail logs for both
make logs

# Stop both
make stop

# Foreground (one at a time, useful for debugging)
make api    # FastAPI only  — http://localhost:8001
make ui     # Next.js only  — http://localhost:3043

# Regenerate apps/api/ports/domain.py from ontology/wsr.ttl
make generate
```

Open **http://localhost:3043** and log in with:

```
demo@example.com
wsr1234!
```

API docs: **http://localhost:8001/docs**

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/flights` | Civil aviation position reports |
| GET | `/api/military` | Military aircraft (ADSB.lol) |
| GET | `/api/mideast-aircraft` | Theater aircraft (airplanes.live) |
| GET | `/api/satellites` | TLE records (CelesTrak) |
| GET | `/api/earthquakes` | M≥1.0 seismic events, past 24 h |
| GET | `/api/news` | RSS aggregation (BBC / Al Jazeera) |
| GET | `/api/conflict-events` | Static OSINT conflict site list |
| GET | `/api/cctv` | Merged camera list (all sources) |
| GET | `/api/cctv/snapshot?url=` | Server-side image/HLS proxy |
| GET | `/api/webcams` | OpenWebcamDB camera list |
| GET | `/api/webcams/stream?slug=` | Stream URL resolver |
| GET | `/health` | Health check |

The Next.js app proxies all `/api/*` calls to the FastAPI backend via `next.config.ts`. No CORS configuration or `NEXT_PUBLIC_API_BASE_URL` needed for local development.

---

## Environment variables

**Backend** (`apps/api/.env` — copy from `.env.example`)

| Variable | Required | Description |
|---|---|---|
| `OPENSKY_CLIENT_ID` | No | OAuth2 client ID for new OpenSky accounts (post-March 2025) |
| `OPENSKY_CLIENT_SECRET` | No | OAuth2 client secret |
| `OPENSKY_USERNAME` | No | Legacy basic-auth for pre-March 2025 accounts |
| `OPENSKY_PASSWORD` | No | Legacy basic-auth password |
| `TFL_APP_KEY` | No | Raises London CCTV rate limit from 60 to 500 req/min |
| `OPENWEBCAMDB_API_KEY` | No | Enables `/api/webcams` and OWDB cameras in `/api/cctv` |
| `ALLOWED_ORIGINS` | No | JSON array of allowed CORS origins, default `["*"]` |

Without any API keys, all free feeds still work: flights via airplanes.live, London CCTV anonymously, USGS earthquakes, CelesTrak satellites, BBC/Al Jazeera news.

**Frontend** (`apps/web/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_CESIUM_TOKEN` | No | Enables Cesium Ion terrain + ESRI satellite imagery. Free at [ion.cesium.com](https://ion.cesium.com) |
| `NEXT_PUBLIC_API_BASE_URL` | No | Override API base URL for non-local deployments |

---

## ABI integration

When loaded as part of an ABI stack (`config.yaml` or `config.local.yaml`):

```yaml
- module: naas_abi_marketplace.alpha.wsr
  enabled: true
  config:
    opensky_client_id: ""
    opensky_client_secret: ""
    tfl_app_key: ""
    openwebcamdb_api_key: ""
```

The `WSRAgent` registers as a chat agent in Nexus under the Agents dropdown. It answers situational awareness queries (conflict zones, flight anomalies, seismic activity, breaking news) and can guide users to the WSR globe.

---

## Ontology

All domain concepts are declared in `ontology/wsr.ttl` using the `wsr:` namespace (`http://ontology.naas.ai/wsr/`) grounded in [BFO 2020](https://basic-formal-ontology.org/).

| BFO bucket | WSR classes |
|---|---|
| Site | `GeographicSite`, `ConflictZone`, `NuclearFacilitySite`, `AirspaceRegion`, `OrbitalShell` |
| Material Entity | `Satellite`, `Aircraft`, `MilitaryAircraft`, `CivilAircraft`, `CCTVCameraUnit` |
| GDC / ICE | `TLERecord`, `AircraftPositionReport`, `EarthquakeEventRecord`, `NewsArticle`, `VideoStream` |
| Process | `FlightTrackingProcess`, `SatelliteTrackingProcess`, `EarthquakeMonitoringProcess`, `CCTVStreamingProcess`, `NewsAggregationProcess` |

Running `make generate` (from `apps/`) converts the TTL into `apps/api/ports/domain.py`.

---

## Contributing

See **[AGENTS.md](./AGENTS.md)** — covers the mandatory ontology-first development order, end-to-end walkthrough for adding a new data layer, naming conventions, caching rules, and what not to do.

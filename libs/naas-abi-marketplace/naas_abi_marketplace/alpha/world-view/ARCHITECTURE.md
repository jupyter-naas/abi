# WorldView — Technical Architecture

> A real-time geospatial intelligence dashboard: Google Earth × Palantir.
> Built from the video brief: live satellite tracking, CCTV feeds, military/commercial flight data,
> seismic activity, and street traffic fused against a 3D model of the Earth in-browser.

---

## 1. Product Feature Matrix

| Feature | Data Source | Update Frequency | Priority |
|---|---|---|---|
| 3D Globe + Google 3D Tiles | Google Tiles API / Cesium Ion | Static | P0 |
| Post-processing shaders (CRT, NVG, Thermal, Bloom) | GLSL — in-browser | — | P0 |
| Points of Interest / Landmark camera snap | OpenStreetMap Overpass API | Static | P0 |
| Keyboard shortcut POI navigation (Q W E R T…) | Client-side | — | P0 |
| Real-time satellite tracking + orbit display | CelesTrak TLE → satellite.js | 1-second client propagation | P0 |
| Click-to-track any satellite | Client-side | — | P0 |
| Live commercial flights | OpenSky Network REST API | 15–30 s polling | P0 |
| Click-to-track any flight | Client-side | — | P0 |
| Military flights (ADSB Exchange) | ADSB Exchange API | 60 s polling | P0 |
| Flight layer filtering (military / civilian) | Client-side | — | P0 |
| Live CCTV feeds (Austin TX) | City of Austin Open Data | 1 frame/min | P1 |
| CCTV projected onto 3D geometry | CesiumJS texture plane | — | P1 |
| Street traffic particle simulation | OpenStreetMap Overpass API | Static road network | P1 |
| Seismic activity layer | USGS Earthquake Hazards API | 5 min polling | P1 |
| Detection mode sparse/full toggle | Client-side | — | P1 |
| Shot planning / keyframe presets | Client-side localStorage | — | P2 |
| City/landmark jump list | Curated + OSM Nominatim | Static | P2 |

---

## 2. Core Technology Decisions

### 2.1 3D Globe Engine — CesiumJS

**Decision:** CesiumJS (not Three.js, not Mapbox, not Google Earth Studio).

**Rationale:**
- Only open-source engine with first-class Google 3D Tiles support (`Cesium.createGooglePhotorealistic3DTileset`).
- Built-in CZML / CZML streaming for satellite/plane entity animation.
- `Cesium.PostProcessStage` for custom GLSL shaders (CRT, NVG, thermal).
- `Cesium.SampledPositionProperty` handles satellite propagation interpolation natively.
- `Cesium.PathGraphics` renders orbital paths with zero additional code.
- `Cesium.BillboardCollection` renders thousands of icons at 60fps.
- `Cesium.PointPrimitiveCollection` is the particle system for street traffic.

**React binding:** Resium (thin React wrapper around CesiumJS, maintained by the Cesium community).

**Frontend framework:** Next.js (matches existing `naas-abi` stack).

### 2.2 Backend — Python FastAPI

**Rationale:**
- Rate-limit aggregation: fan-out to multiple APIs, cache results, serve a single endpoint to the frontend.
- OpenSky: max 10 req/10s authenticated — backend pools requests across all clients.
- ADSB Exchange: API key required — never expose in frontend.
- CCTV proxy: CORS issues with direct browser fetch; backend proxies image streams.
- Fits hexagonal architecture pattern of the existing monorepo.

**WebSocket vs polling:** Use Server-Sent Events (SSE) for flight/satellite push; REST polling for seismic.

### 2.3 Satellite Propagation — satellite.js

CelesTrak publishes TLE (Two-Line Element) sets for every tracked object.
`satellite.js` (JavaScript port of SGP4/SDP4) propagates positions from TLEs in-browser, eliminating any backend round-trip for real-time position updates.

```
TLE fetch (backend, cached 1h) → sent to client once
satellite.js propagates position every 1s client-side → entity position updated in Cesium
```

---

## 3. Data Source Integration

### 3.1 Satellites — CelesTrak

- **URL:** `https://celestrak.org/SOCRATES/query.php` (active sats) or GP feed
- **Format:** TLE text, JSON GP (`application/json`)
- **Key endpoints:**
  - All active: `https://celestrak.org/SOCRATES/query.php?CATNR=all&FORMAT=JSON`
  - By group: `https://celestrak.org/TLE/table.php?GROUP=active&FORMAT=JSON`
- **Update cadence:** TLEs valid ~2 weeks; refresh every 1 hour is sufficient.
- **Client propagation:** `satellite.propagate(satrec, date)` → ECI → ECF → lat/lon/alt.

```typescript
// satellite.js propagation loop
import * as satellite from 'satellite.js';

const satrec = satellite.twoline2satrec(line1, line2);

setInterval(() => {
  const now = new Date();
  const posVel = satellite.propagate(satrec, now);
  const gmst = satellite.gstime(now);
  const geo = satellite.eciToGeodetic(posVel.position, gmst);
  // geo.longitude, geo.latitude, geo.height → Cesium Cartesian3
}, 1000);
```

### 3.2 Commercial Flights — OpenSky Network

- **Base URL:** `https://opensky-network.org/api`
- **Key endpoint:** `GET /states/all` → returns all ~9k aircraft states
- **Auth:** Anonymous (free, rate-limited) or Basic Auth (registered, higher limits)
- **Response fields:** `icao24`, `callsign`, `origin_country`, `longitude`, `latitude`, `baro_altitude`, `velocity`, `heading`
- **Rate limit:** 10 req/10s (registered), 5 req/10s (anonymous)
- **Backend caches:** 30s, serves all frontend clients from single poll.

```python
# OpenSky adapter
class OpenSkyAdapter(IFlightPort):
    BASE_URL = "https://opensky-network.org/api"

    async def get_all_flights(self) -> list[FlightState]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.BASE_URL}/states/all",
                                 auth=(self.username, self.password))
        return [FlightState.from_opensky(s) for s in r.json()["states"]]
```

### 3.3 Military Flights — ADSB Exchange

- **URL:** `https://adsbexchange.com/api/aircraft/json/` (requires API key)
- **Alternative free tier:** `https://api.adsb.lol/v2/all` (community ADSB.lol, no key needed)
- **Filter military:** `military=true` flag or filter by hex ranges known to military.
- **Alternative OSINT approach:** filter aircraft with no callsign + known ICAO military hex ranges.
- **ADSB.lol (free):** `GET https://api.adsb.lol/v2/all` → same OpenSky-compatible schema.

### 3.4 CCTV Cameras — City of Austin

- **Open data portal:** `https://data.austintexas.gov`
- **Traffic camera dataset ID:** `b4k4-adkb` (Mobility Camera Locations)
- **Camera image API:** `https://cctv.austintexas.gov/api/` or direct JPEG endpoint per camera
- **Image format:** Static JPEG, 1 frame/minute
- **Backend proxy:** Required for CORS. Backend polls each active camera, caches image + timestamp.
- **Projection onto 3D:** Use `Cesium.Entity` with `plane` graphic + `Cesium.ImageMaterialProperty`.

```typescript
// Project CCTV image onto a vertical plane at camera coordinates
viewer.entities.add({
  position: Cesium.Cartesian3.fromDegrees(lon, lat, 5),
  plane: {
    plane: new Cesium.Plane(Cesium.Cartesian3.UNIT_Z, 0),
    dimensions: new Cesium.Cartesian2(20, 15),
    material: new Cesium.ImageMaterialProperty({
      image: `/api/cctv/camera/${cameraId}/latest`,
    }),
  },
});
```

### 3.5 Seismic Activity — USGS

- **URL:** `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/`
- **Key feeds (GeoJSON):**
  - All earthquakes last hour: `all_hour.geojson`
  - All earthquakes last day: `all_day.geojson`
  - All earthquakes last 7 days: `all_week.geojson`
  - Significant last month: `significant_month.geojson`
- **Completely free, no auth.**
- **Frontend:** Render as `Cesium.Entity` cylinders scaled by magnitude.

### 3.6 Street Traffic Particle System — OpenStreetMap

- **Overpass API:** `https://overpass-api.de/api/interpreter`
- **Query strategy** (sequential loading, per the video to avoid browser crash):

```
Step 1: Fetch motorways + trunk roads (low volume, loads fast)
Step 2: Fetch primary + secondary roads
Step 3: Fetch arterial / residential (high volume, load last)
```

- **Overpass query example:**
```
[out:json][timeout:30];
way["highway"~"motorway|trunk"]({{bbox}});
out geom;
```
- **Particle system:** `Cesium.PointPrimitiveCollection` — spawn points along road segments,
  animate along path with random speed variation. No actual traffic data needed; it's visual emulation.

---

## 4. Post-Processing Shaders

All effects implemented as `Cesium.PostProcessStage` with custom GLSL fragment shaders.

### 4.1 CRT Effect
```glsl
// crt.frag
uniform sampler2D colorTexture;
uniform float scanlineIntensity;   // 0.0–1.0
uniform float pixelation;          // 1–8

in vec2 v_textureCoordinates;

void main() {
  vec2 uv = v_textureCoordinates;
  // Pixelation
  float px = pixelation / czm_viewport.z;
  float py = pixelation / czm_viewport.w;
  uv = floor(uv / vec2(px, py)) * vec2(px, py);
  vec4 color = texture(colorTexture, uv);
  // Scanlines
  float scanline = sin(uv.y * czm_viewport.w * 3.14159) * 0.5 + 0.5;
  color.rgb *= mix(1.0, scanline, scanlineIntensity);
  // Vignette
  vec2 center = uv - 0.5;
  color.rgb *= 1.0 - dot(center, center) * 1.5;
  out_FragColor = color;
}
```

### 4.2 Night Vision (NVG Green Phosphor)
```glsl
// nvg.frag
uniform sampler2D colorTexture;
uniform float sensitivity;   // 1.0–5.0 (amplification)
uniform float noise;         // 0.0–1.0

void main() {
  vec2 uv = v_textureCoordinates;
  vec4 color = texture(colorTexture, uv);
  // Luminance → green channel amplified
  float lum = dot(color.rgb, vec3(0.299, 0.587, 0.114)) * sensitivity;
  // Add grain
  float grain = fract(sin(dot(uv * 1000.0, vec2(12.9898, 78.233))) * 43758.5453);
  lum += (grain - 0.5) * noise * 0.3;
  out_FragColor = vec4(0.0, clamp(lum, 0.0, 1.0), 0.0, 1.0);
}
```

### 4.3 Thermal Imaging
```glsl
// thermal.frag
// Maps luminance to FLIR-style palette: black → blue → green → yellow → red → white
uniform sampler2D colorTexture;

vec3 thermalPalette(float t) {
  if (t < 0.25) return mix(vec3(0,0,0), vec3(0,0,1), t * 4.0);
  if (t < 0.5)  return mix(vec3(0,0,1), vec3(0,1,0), (t - 0.25) * 4.0);
  if (t < 0.75) return mix(vec3(0,1,0), vec3(1,1,0), (t - 0.5)  * 4.0);
  return            mix(vec3(1,1,0), vec3(1,0,0), (t - 0.75) * 4.0);
}

void main() {
  vec4 color = texture(colorTexture, v_textureCoordinates);
  float lum = dot(color.rgb, vec3(0.299, 0.587, 0.114));
  out_FragColor = vec4(thermalPalette(lum), 1.0);
}
```

### 4.4 Bloom
CesiumJS has `Cesium.PostProcessStageLibrary.createBloomStage()` built-in.
```typescript
viewer.postProcessStages.add(
  Cesium.PostProcessStageLibrary.createBloomStage()
);
```

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Next.js / React)                 │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  CesiumJS Viewer                      │  │
│  │                                                      │  │
│  │  Google 3D Tiles │ Satellite Entities │ Flight Blls  │  │
│  │  CCTV Planes     │ Seismic Cylinders  │ Traffic Pts  │  │
│  │                                                      │  │
│  │           PostProcessStage pipeline:                 │  │
│  │      [CRT] → [NVG] → [Thermal] → [Bloom]            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  satellite.js│  │  React UI Layer  │  │  Data Hooks  │  │
│  │  (SGP4 loop) │  │  Panels/Controls │  │  useSat,     │  │
│  │  1s interval │  │  Sidebar, HUD    │  │  useFlights  │  │
│  └─────────────┘  └──────────────────┘  └──────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST / SSE
┌──────────────────────────────▼──────────────────────────────┐
│                  Python FastAPI Backend                       │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              WorldViewService (Domain)                  │ │
│  │                                                        │ │
│  │  aggregate_flights() → merge OpenSky + ADSB military   │ │
│  │  get_satellites()    → TLE cache, refresh every 1h     │ │
│  │  get_cctv_frame()    → proxy + cache per camera        │ │
│  │  get_earthquakes()   → USGS feed cache 5min            │ │
│  │  get_road_network()  → Overpass query + tile cache     │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Ports (interfaces):                                        │
│    IFlightPort │ ISatellitePort │ ICCTVPort │ ISeismicPort  │
│                                                             │
│  Secondary Adapters:                                        │
│    OpenSkyAdapter │ ADSBAdapter │ CelesTrakAdapter         │
│    AustinCCTVAdapter │ USGSAdapter │ OverpassAdapter       │
│                                                             │
│  Cache: Redis (or Python in-memory for dev)                 │
└─────────────────────────────────────────────────────────────┘
            │               │            │          │
     OpenSky API      CelesTrak     ADSB Exchange  USGS
     opensky-network  celestrak.org adsb.lol       earthquake.usgs.gov
            │               │            │          │
     Austin Open Data   OSM Overpass
     data.austintexas.gov  overpass-api.de
```

---

## 6. File Structure

```
world-view/
├── BRIEF.md
├── ARCHITECTURE.md              ← this file
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── public/
│   │   └── cesium/              ← Cesium static assets (Workers, Assets, Widgets)
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   └── page.tsx         ← Mounts <WorldView />
│       ├── components/
│       │   ├── WorldView.tsx    ← Root: initializes CesiumViewer, mounts all layers
│       │   ├── Globe.tsx        ← Cesium viewer + 3D Tiles init
│       │   ├── ShaderPanel.tsx  ← CRT/NVG/Thermal/Bloom toggle + sliders
│       │   ├── DataLayerPanel.tsx  ← Layer toggles sidebar (sats, flights, CCTV...)
│       │   ├── TrackingOverlay.tsx ← Entity info HUD when tracking a satellite/plane
│       │   ├── CCTVPanel.tsx    ← List of cameras + projector controls
│       │   └── POIPanel.tsx     ← Points of interest keyboard shortcuts
│       ├── hooks/
│       │   ├── useSatellites.ts ← Fetch TLEs, propagate with satellite.js
│       │   ├── useFlights.ts    ← Poll backend /api/flights every 30s
│       │   ├── useFlightsMilitary.ts
│       │   ├── useEarthquakes.ts
│       │   ├── useStreetTraffic.ts  ← Overpass road fetch + particle animation
│       │   └── useCCTV.ts
│       ├── layers/
│       │   ├── SatelliteLayer.tsx   ← Cesium BillboardCollection for sats
│       │   ├── FlightLayer.tsx      ← Cesium BillboardCollection for planes
│       │   ├── EarthquakeLayer.tsx  ← Cesium cylinder entities
│       │   ├── TrafficLayer.tsx     ← Cesium PointPrimitiveCollection
│       │   └── CCTVLayer.tsx        ← Cesium plane entities with image material
│       ├── shaders/
│       │   ├── crt.glsl
│       │   ├── nightvision.glsl
│       │   ├── thermal.glsl
│       │   └── flare.glsl
│       ├── data/
│       │   └── landmarks.ts     ← Curated POI list: city, landmark, lat/lon/alt/heading
│       └── lib/
│           ├── cesium.ts        ← Cesium init, Ion token, Google Tiles
│           ├── satellite-utils.ts  ← TLE parsing + propagation helpers
│           └── osm.ts           ← Overpass query builders
├── backend/
│   ├── pyproject.toml
│   ├── main.py                  ← FastAPI app entry
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── IFlightPort.py
│   │   ├── ISatellitePort.py
│   │   ├── ICCTVPort.py
│   │   ├── ISeismicPort.py
│   │   └── IRoadNetworkPort.py
│   ├── adapters/
│   │   ├── secondary/
│   │   │   ├── OpenSkyAdapter.py
│   │   │   ├── ADSBAdapter.py
│   │   │   ├── CelesTrakAdapter.py
│   │   │   ├── USGSAdapter.py
│   │   │   ├── AustinCCTVAdapter.py
│   │   │   └── OverpassAdapter.py
│   │   └── primary/
│   │       └── FastAPIAdapter.py    ← Route definitions
│   ├── domain/
│   │   ├── WorldViewService.py
│   │   ├── models.py            ← FlightState, SatelliteRecord, EarthquakeEvent...
│   │   └── cache.py             ← TTL cache wrapper
│   └── factories/
│       └── WorldViewFactory.py  ← Wire adapters to service
```

---

## 7. Key Implementation Steps

### Step 1 — Frontend Scaffold
```bash
cd world-view
npx create-next-app@latest frontend --typescript --tailwind --app
cd frontend
npm install cesium resium satellite.js
npm install -D copy-webpack-plugin
```

Configure `next.config.js` to copy Cesium static assets:
```js
const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
  webpack(config) {
    config.plugins.push(
      new CopyPlugin({
        patterns: [
          { from: 'node_modules/cesium/Build/Cesium/Workers', to: 'static/cesium/Workers' },
          { from: 'node_modules/cesium/Build/Cesium/Assets', to: 'static/cesium/Assets' },
          { from: 'node_modules/cesium/Build/Cesium/Widgets', to: 'static/cesium/Widgets' },
        ],
      })
    );
    return config;
  },
};
```

### Step 2 — Globe + Google 3D Tiles
```typescript
// lib/cesium.ts
import * as Cesium from 'cesium';

export function initCesium(container: HTMLDivElement): Cesium.Viewer {
  Cesium.Ion.defaultAccessToken = process.env.NEXT_PUBLIC_CESIUM_TOKEN!;

  const viewer = new Cesium.Viewer(container, {
    terrain: Cesium.Terrain.fromWorldTerrain(),
    timeline: false,
    animation: false,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
  });

  // Google Photorealistic 3D Tiles
  viewer.scene.primitives.add(
    await Cesium.createGooglePhotorealistic3DTileset({
      onlyUsingWithGooglePhotorealisticTiles: true,
    })
  );

  return viewer;
}
```

### Step 3 — Satellite Layer
```typescript
// hooks/useSatellites.ts
import * as satellite from 'satellite.js';

export function useSatellites(viewer: Cesium.Viewer | null) {
  useEffect(() => {
    if (!viewer) return;
    // Fetch TLEs from backend (cached hourly)
    const tles = await fetch('/api/satellites').then(r => r.json());

    const satrecs = tles.map(({ name, line1, line2 }) => ({
      name,
      satrec: satellite.twoline2satrec(line1, line2),
    }));

    const billboards = viewer.scene.primitives.add(
      new Cesium.BillboardCollection({ scene: viewer.scene })
    );

    const interval = setInterval(() => {
      const now = new Date();
      const gmst = satellite.gstime(now);
      billboards.removeAll();
      satrecs.forEach(({ name, satrec }) => {
        const pv = satellite.propagate(satrec, now);
        if (!pv.position) return;
        const geo = satellite.eciToGeodetic(pv.position, gmst);
        billboards.add({
          position: Cesium.Cartesian3.fromRadians(geo.longitude, geo.latitude, geo.height * 1000),
          image: '/icons/satellite.png',
          width: 12,
          height: 12,
        });
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [viewer]);
}
```

### Step 4 — Post-Processing Stage (CRT example)
```typescript
// components/ShaderPanel.tsx
const crtStage = new Cesium.PostProcessStage({
  fragmentShader: crtGLSL,   // import raw string from shaders/crt.glsl
  uniforms: {
    scanlineIntensity: () => scanlineIntensity,
    pixelation: () => pixelation,
  },
});
viewer.postProcessStages.add(crtStage);
crtStage.enabled = false;  // toggle on/off
```

### Step 5 — Backend Bootstrap
```bash
cd world-view/backend
uv init
uv add fastapi uvicorn httpx pydantic redis
```

```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from adapters.primary.FastAPIAdapter import router

app = FastAPI(title="WorldView API")
app.add_middleware(CORSMiddleware, allow_origins=["*"])
app.include_router(router, prefix="/api")
```

### Step 6 — POI Keyboard Navigation
```typescript
// data/landmarks.ts
export const LANDMARKS = {
  'new-york': {
    name: 'New York City',
    pois: [
      { key: 'q', name: 'Empire State Building', lat: 40.7484, lon: -73.9967, alt: 500, heading: 0 },
      { key: 'w', name: 'Statue of Liberty',     lat: 40.6892, lon: -74.0445, alt: 200, heading: 90 },
      // ...
    ],
  },
  // ...
};

// In Globe.tsx — keyboard handler
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    const poi = currentCityPois.find(p => p.key === e.key);
    if (!poi) return;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(poi.lon, poi.lat, poi.alt),
      orientation: { heading: Cesium.Math.toRadians(poi.heading), pitch: Cesium.Math.toRadians(-30) },
      duration: 2,
    });
  };
  window.addEventListener('keydown', handler);
  return () => window.removeEventListener('keydown', handler);
}, [viewer, currentCityPois]);
```

---

## 8. API Keys Required

| Service | Key Required | Free Tier | Where |
|---|---|---|---|
| Cesium Ion | Yes | Free | ion.cesium.com |
| Google 3D Tiles | Yes | Free ($200/mo credit) | cloud.google.com/maps-platform |
| OpenSky Network | Optional | Yes (lower rate limit) | opensky-network.org |
| ADSB.lol | No | Yes | api.adsb.lol |
| ADSB Exchange | Yes (better data) | Limited | rapidapi.com/adsbx |
| USGS Earthquake | No | Yes | earthquake.usgs.gov |
| Austin Open Data | No | Yes | data.austintexas.gov |
| CelesTrak | No | Yes | celestrak.org |
| OSM Overpass | No | Yes (fair use) | overpass-api.de |

**Total cost to run: $0** using free tiers for a personal/demo instance.

---

## 9. UI Design — Classified Intelligence Aesthetic

- **Color palette:** `#00ff41` (terminal green) on `#000000`, with `#ff6600` for military alerts.
- **Typography:** Monospace (`JetBrains Mono` or `Space Mono`).
- **Panel style:** Semi-transparent dark (`bg-black/60 backdrop-blur-sm border border-green-500/30`).
- **Data readouts:** All values formatted as fixed-width monospace (lat/lon to 4 decimal places, altitude in meters, speed in knots).
- **Crosshair:** Fixed SVG crosshair overlay at viewport center.
- **Status bar:** Top bar showing current UTC time, active layer count, entity count.
- **Mode indicator:** Top-left badge cycling through `NORMAL` / `NVG` / `THERMAL` / `CRT`.

---

## 10. Build Order (Execution Sequence)

1. **Day 1 — Globe + Shaders**
   - CesiumJS init + Google 3D Tiles
   - Basic UI shell (dark theme, panels)
   - CRT + NVG + Thermal post-process stages with slider controls
   - POI landmark list + keyboard navigation

2. **Day 2 — Live Data Layers**
   - Backend scaffold (FastAPI + adapters)
   - Satellite layer (CelesTrak TLEs + satellite.js propagation)
   - Commercial flights layer (OpenSky)
   - Click-to-track for satellites and flights (orbit path + tracking camera)
   - Military flights (ADSB Exchange / ADSB.lol)

3. **Day 3 — Immersive Layers**
   - CCTV integration (Austin TX open data) + projection onto 3D geometry
   - Street traffic particle system (Overpass + PointPrimitiveCollection)
   - Seismic activity layer (USGS)
   - Shot planning / preset keyframes (localStorage)
   - Polish: bloom, flare effects, detection mode sparse/full toggle

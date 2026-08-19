# WSR — Architecture & Ontology Reference

## Why This Document Exists

WSR started as a 1000-line `WSR.tsx` that mixed WebGL rendering,
REST polling, state management, and business logic into a single file. That works
until it doesn't — and it stops working fast when:

- A new data source needs to be added
- A process interval needs to change globally
- A conflict site needs to be referenced by two different systems
- An analyst asks "which processes touch Natanz?"

This document describes the **BFO-grounded refactoring** that prevents that
entropy, explains every file in the ontology layer, and shows how the TypeScript
code maps to formal OWL axioms.

---

## BFO 7-Bucket Map for WSR

Every concept in WSR belongs to exactly one BFO bucket.
These are not architectural layers — they are ontological categories.

| Bucket | BFO Class | IRI | WSR Examples |
|---|---|---|---|
| **WHERE** | Site | `BFO_0000029` | `ConflictZone`, `NuclearFacilitySite`, `OrbitalShell` |
| **WHO** | Material Entity | `BFO_0000040` | `Satellite`, `Aircraft`, `CCTVCameraUnit`, `DataSourceEndpoint` |
| **HOW WE KNOW** | Generically Dependent Continuant | `BFO_0000031` | `TLERecord`, `AircraftPositionReport`, `NewsArticle`, `VideoStream` |
| **HOW IT IS** | Quality | `BFO_0000019` | `GeographicCoordinate`, `ThreatSeverityLevel`, `EarthquakeMagnitude` |
| **WHY (external)** | Role | `BFO_0000023` | `SurveillanceSourceRole`, `IntelligenceSourceRole`, `TheaterActorRole` |
| **WHY (internal)** | Disposition | `BFO_0000016` | `StreamingDisposition`, `ADSBTransponderDisposition`, `OrbitalPropagationDisposition` |
| **WHAT** | Process | `BFO_0000015` | `SatelliteTrackingProcess`, `NewsAggregationProcess`, `ThreatAssessmentProcess` |

---

## File Structure

```
wsr/
├── ontology/
│   ├── wsr.ttl              # Class hierarchy — BFO subclasses for all WSR concepts
│   └── wsr-instances.ttl   # Named individuals — specific sites, endpoints, process instances
│
└── frontend/src/
    ├── lib/
    │   ├── types.ts               # Legacy types (kept for backward compat, map to ontology.ts)
    │   └── ontology.ts            # BFO-aligned TS interfaces mirroring wsr.ttl
    │
    ├── hooks/
    │   ├── useFlightData.ts       # wv:FlightTrackingProcess + wv:TheaterAircraftMonitoringProcess
    │   ├── useEarthquakes.ts      # wv:EarthquakeMonitoringProcess
    │   └── useConflictIntel.ts    # wv:NewsAggregationProcess → wv:ThreatAssessmentProcess
    │
    ├── components/
    │   ├── WSR.tsx          # Cesium orchestrator (to be split — see roadmap below)
    │   └── ui/
    │       ├── IntelPanel.tsx     # Renders wv:NewsArticle + wv:ConflictSiteRecord
    │       ├── CCTVPanel.tsx      # Renders wv:VideoStream from wv:CCTVCameraUnit
    │       ├── GeoSearch.tsx      # Triggers wv:GeocodingProcess
    │       ├── StatusBar.tsx      # Displays qualities of current globe state
    │       ├── TrackingOverlay.tsx # Renders qualities of tracked material entity
    │       ├── ShaderPanel.tsx    # Controls wv:GlobeRenderingProcess shader stage
    │       └── DataLayerPanel.tsx # Toggles layer visibility
    │
    ├── app/api/
    │   ├── satellites/route.ts    # ICE: wv:TLERecord — source: CelesTrak
    │   ├── flights/route.ts       # ICE: wv:AircraftPositionReport — source: OpenSky
    │   ├── military/route.ts      # ICE: wv:MilitaryAircraftReport — source: ADSB.lol
    │   ├── mideast-aircraft/route.ts # ICE: wv:MilitaryAircraftReport — source: airplanes.live
    │   ├── earthquakes/route.ts   # ICE: wv:EarthquakeEventRecord — source: USGS
    │   ├── news/route.ts          # ICE: wv:NewsArticle — source: BBC/AJ/Reuters RSS
    │   ├── conflict-events/route.ts # ICE: wv:ConflictSiteRecord — source: OSINT static
    │   ├── cctv/route.ts          # Material: wv:CCTVCameraUnit catalog
    │   ├── cctv/snapshot/route.ts # Process: wv:CCTVStreamingProcess proxy
    │   ├── webcams/route.ts       # ICE: OpenWebcamDB stream catalog
    │   └── webcams/stream/route.ts # Process: on-demand stream URL resolution
    │
    └── data/
        └── landmarks.ts           # Site: city/landmark geographic coordinates
```

---

## Ontology Files — What They Do

### `ontology/wsr.ttl` — Class Hierarchy

Defines every WSR-specific OWL class as a subclass of the appropriate
BFO class. The file is organized into 7 sections — one per BFO bucket.

Key design decisions:
- `wv:ConflictZone` subclasses `wv:GeographicSite` subclasses `BFO_0000029` (Site)
- `wv:DataSourceEndpoint` is a **material entity** (physical server), not a GDC
- `wv:NewsArticle` is a **GDC** (information content), not a material entity
- `wv:ThreatSeverityLevel` is a **quality** that **inheres in** news articles
- `wv:ThreatAssessmentProcess` has `precededBy` wv:NewsAggregationProcess (temporal ordering)

### `ontology/wsr-instances.ttl` — Named Individuals

Every concrete entity in the WSR system that has a stable identity:

**Sites (17 named individuals)**
- All Iranian nuclear sites (Natanz, Fordow, Isfahan, Arak, Bushehr)
- Israeli military/nuclear sites (Dimona, Nevatim, Haifa)
- US CENTCOM bases (Al Udeid, Al Dhafra, Persian Gulf CSG area)
- Regional flashpoints (Beirut, Damascus corridor)

**Data Source Endpoints (9 named individuals)**
- CelesTrak, OpenSky, ADSB.lol, airplanes.live, USGS
- BBC, Al Jazeera, Reuters RSS feeds
- Nominatim geocoder

**Process Instances (7 named individuals)**
- One per BFO process subclass, carrying `wv:hasRefreshInterval` assertions

---

## TypeScript → OWL Mapping

### `lib/ontology.ts` — The Bridge

Every BFO class has a corresponding TypeScript interface. Every named individual
has a typed constant. This file is the **single source of truth** for:

1. **Polling intervals** — `WSR_PROCESSES[processType].refreshIntervalMs`  
   Change it here, it changes in the code AND is documented at the ontology level.

2. **Conflict site IRIs** — `CONFLICT_SITE_IRI_MAP`  
   Maps legacy string IDs (e.g. `'natanz'`) to canonical `wvi:` IRIs.  
   This is how the IntelPanel links to the formal ontology.

3. **Threat level computation** — `computeThreatLevel(breakingCount)`  
   Encoded as a pure function that realizes `wv:ThreatAssessmentProcess`.

### Type migration path

The old types in `lib/types.ts` map to the new ontology types as follows:

| Old type (`lib/types.ts`) | New type (`lib/ontology.ts`) | BFO Bucket |
|---|---|---|
| `SatelliteRecord` | `TLERecord` | GDC |
| `FlightState` | `AircraftPositionReport` | GDC |
| `EarthquakeFeature` | `EarthquakeEventRecord` | GDC |
| `CCTVCamera` | `OntologyCCTVCameraUnit` | Material Entity |
| `NewsItem` | `NewsArticle` | GDC |
| `ConflictEvent` | `ConflictSiteRecord` | GDC |
| `TrackedEntity` | `OntologyAircraft` / `OntologySatellite` | Material Entity |

**Migration is incremental.** Old types are not deleted — the new interfaces
extend and type-check against the same data shapes returned by the API.

---

## Data Hooks — Process Isolation

### Pattern

Each hook = one BFO process class. One clear contract:
- **Input**: `enabled: boolean` (layer toggle)
- **Output**: typed ICEs (information content entities) + counts
- **Side effect**: polls at the interval defined in `WSR_PROCESSES`

### `hooks/useFlightData.ts`

Realizes: `wv:FlightTrackingProcess` + `wv:TheaterAircraftMonitoringProcess`

```
/api/flights        → civil[]     (30s)   — OpenSky
/api/military       → military[]  (60s)   — ADSB.lol  
/api/mideast-aircraft → theater[] (45s)  — airplanes.live
```

### `hooks/useEarthquakes.ts`

Realizes: `wv:EarthquakeMonitoringProcess`

```
/api/earthquakes → earthquakes[] (5min) — USGS
```

### `hooks/useConflictIntel.ts`

Realizes: `wv:NewsAggregationProcess` → `wv:ThreatAssessmentProcess`

```
/api/news             → news[]         (3min) — BBC/AJ/Reuters
/api/conflict-events  → conflictSites[] (once) — OSINT static
                      → threatLevel           — computed quality
```

---

## Architecture Refactoring Roadmap

This is where we are, and where we need to go. Everything works now.
The roadmap shows how to get to zero-coupling without any big-bang rewrite.

### Phase 0 — Done ✓
- [x] `ontology/wsr.ttl` — BFO class hierarchy
- [x] `ontology/wsr-instances.ttl` — named individuals for all sites and endpoints
- [x] `lib/ontology.ts` — TypeScript mirror of TTL
- [x] `hooks/useFlightData.ts` — flight process hook
- [x] `hooks/useEarthquakes.ts` — earthquake process hook
- [x] `hooks/useConflictIntel.ts` — intel + threat assessment hook

### Phase 1 — Extract Cesium rendering out of WSR.tsx
Split the monolith into:
```
components/
  WSR.tsx           ← reduced to orchestrator (data wiring only)
  globe/
    GlobeCanvas.tsx       ← Cesium viewer init, camera, shaders
    BillboardLayer.tsx    ← satellite / flight / CCTV billboard collections
    ConflictLayer.tsx     ← conflict zone ellipses and labels
    BorderLayer.tsx       ← GeoJSON country borders
    EarthquakeLayer.tsx   ← magnitude ellipses
```

### Phase 2 — Migrate WSR.tsx to use the new hooks
Replace inline `useEffect` fetch blocks with:
```tsx
const { civil, military, theater } = useFlightData({ ... });
const { earthquakes }              = useEarthquakes(showEarthquakes);
const { news, conflictSites, threatLevel } = useConflictIntel();
```

### Phase 3 — Add provenance to API responses
Wrap API route responses in a provenance envelope:
```typescript
interface ProvenanceEnvelope<T> {
  data: T;
  fetchedAt: number;          // Unix ms
  sourceIri: string;          // wvi: endpoint IRI
  processIri: string;         // wvi: process instance IRI
  cacheTTLMs: number;
}
```

### Phase 4 — Semantic cross-layer correlation
Enable queries like "show me military aircraft currently inside a ConflictZone":
```typescript
function aircraftInZone(
  aircraft: AircraftPositionReport[],
  zone: GeographicSite,
  radiusKm: number,
): AircraftPositionReport[] { ... }
```
This is the payoff of the ontology — the type system enforces that you can
only call this with a `GeographicSite`, not a `DataSourceEndpoint`.

---

## Adding a New Data Source — Protocol

1. **Determine BFO bucket**: Is it a Site, Material Entity, GDC, Quality, Role, Disposition, or Process?
2. **Add a class to `wsr.ttl`**: `wv:NewClass rdfs:subClassOf <bfo:class> .`
3. **Add a named individual to `wsr-instances.ttl`** if it's a concrete endpoint or site.
4. **Add the TypeScript interface to `lib/ontology.ts`** extending the correct BFO base interface.
5. **Add the process descriptor to `WSR_PROCESSES`** if it introduces a new polling cycle.
6. **Create the API route** producing the ICE.
7. **Create or extend a hook** realizing the process.

That's the discipline. Skip step 1 and you're back to the big ball of mud.

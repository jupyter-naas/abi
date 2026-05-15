# WSR — Agent and Contributor Guide

Read this completely before making any change. Every rule exists because a deviation caused a real bug or architectural regression.

---

## 1. Mental model

WSR is a **real-time geospatial intelligence fuser**. The globe is the UI. Data flows in from external APIs, gets normalised, and gets rendered as Cesium primitives. The architecture enforces a strict separation of concerns at every layer boundary.

```
External APIs
    ↓  (adapter — infrastructure boundary)
apps/api services  →  FastAPI routers  →  JSON over HTTP
    ↓  (Next.js proxy rewrite — /api/* → localhost:8001)
apps/web GlobeEngine
    ↓  (layer adapter — Cesium boundary)
Cesium WebGL primitives  →  Analyst's screen
```

**Every concept is grounded in BFO.** Before writing any code, identify the BFO bucket:

| BFO bucket | What goes here |
|---|---|
| **Site** (BFO_0000029) | Geographic regions, airspace, orbital shells |
| **Material Entity** (BFO_0000040) | Physical objects: aircraft, satellites, cameras, vessels |
| **GDC / ICE** (BFO_0000031) | Information: TLE records, position reports, news, video streams |
| **Quality** (BFO_0000019) | Measurable properties: magnitude, altitude, heading, severity |
| **Role** (BFO_0000023) | Institutional function: surveillance source, tracking target |
| **Disposition** (BFO_0000016) | Physical capability: ADS-B transponder, orbital propagation |
| **Process** (BFO_0000015) | What the system does: tracking, aggregation, streaming, rendering |

---

## 2. Non-negotiable development order

Every feature addition follows this exact sequence. Skip a step and you break the source-of-truth chain.

```
1. ontology/wsr.ttl              ← declare the concept FIRST
        ↓ make generate (from apps/)
2. apps/api/ports/domain.py      ← auto-generated, NEVER hand-edited
        ↓ hand-write DTO
3. apps/api/ports/models.py      ← API DTO — clean field names, JSON aliases
        ↓ implement
4. apps/api/services/{domain}/   ← Port → Service → adapters/
        ↓ register
5. apps/api/routers/{domain}.py  ← thin HTTP layer
        ↓ wire
6. apps/api/main.py              ← include_router()
        ↓ fetch in frontend
7. apps/web/src/lib/globe/adapters/data/{Domain}DataSource.ts
        ↓ render
8. apps/web/src/lib/globe/adapters/layers/{Domain}LayerAdapter.ts
        ↓ register in
9. apps/web/src/components/WSR.tsx
```

---

## 3. Ontology — `ontology/wsr.ttl`

### Rules

- All new classes use the `wsr:` prefix (`http://ontology.naas.ai/wsr/`).
- Every class needs `rdfs:label` (English), `skos:definition`, and `rdfs:subClassOf` pointing to a BFO class or a `wsr:` parent.
- Every data property needs `rdfs:domain`, `rdfs:range`, `rdfs:label`, and `skos:definition`.
- Do not add instances to `wsr.ttl` — they go in `wsr-instances.ttl`.

### Regenerate after any TTL edit

```bash
# from apps/
make generate
```

This runs `onto2py.py` and overwrites `apps/api/ports/domain.py` entirely. Never edit that file by hand.

### Example

```turtle
wsr:DroneUnit a owl:Class ;
  rdfs:subClassOf wsr:Aircraft ;
  rdfs:label "Drone Unit"@en ;
  skos:definition "An unmanned aerial vehicle tracked via ADS-B or RF signal." @en .
```

---

## 4. Backend — `apps/api/`

### Directory structure

```
apps/api/
├── core/
│   ├── cache.py          # TTLCache[T] — use this, never invent new caches
│   └── http_client.py    # shared httpx.AsyncClient — never create new clients
├── ports/
│   ├── domain.py         # AUTO-GENERATED — run make generate, do not edit
│   └── models.py         # hand-written API DTOs
├── services/
│   └── {domain}/
│       ├── __init__.py      # singleton: service = MyService(adapters=[...])
│       ├── {Domain}Port.py  # I{X}Adapter + I{X}Service interfaces
│       ├── {Domain}Service.py
│       └── adapters/
│           └── {source}.py  # one file per external data source
├── routers/
│   └── {domain}.py       # HTTP delivery only
├── settings.py           # pydantic-settings — all env vars here
└── main.py               # app + middleware + include_router() calls
```

### Adding a new data layer

**Step 1 — Port** (`services/{domain}/{Domain}Port.py`)

```python
from ports.models import MyNewType

class IMyAdapter:
    async def fetch(self) -> list[MyNewType]:
        raise NotImplementedError

class IMyService:
    async def get_items(self) -> list[MyNewType]:
        raise NotImplementedError
```

**Step 2 — Adapter** (`services/{domain}/adapters/{source}.py`)

```python
from core.cache import TTLCache
from core.http_client import get_client
from ports.models import MyNewType
from services.{domain}.{Domain}Port import IMyAdapter

_HEADERS = {"User-Agent": "WSR-Intel/1.0"}

class SourceXAdapter(IMyAdapter):
    def __init__(self) -> None:
        self._cache: TTLCache[list[MyNewType]] = TTLCache(ttl_seconds=60)

    async def fetch(self) -> list[MyNewType]:
        return await self._cache.get_or_fetch("key", self._fetch)

    async def _fetch(self) -> list[MyNewType]:
        resp = await get_client().get("https://api.example.com/data",
                                      headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        return [MyNewType(id=item["id"], ...) for item in resp.json()]
```

Adapter rules: always set `User-Agent`. Return empty list on failure. Never import from `routers/` or other service domains. Never call `get_client()` outside an `async` method.

**Step 3 — Service** (`services/{domain}/{Domain}Service.py`)

```python
import asyncio, logging
from ports.models import MyNewType
from services.{domain}.{Domain}Port import IMyAdapter, IMyService

log = logging.getLogger(__name__)

class MyService(IMyService):
    def __init__(self, adapters: list[IMyAdapter]) -> None:
        self._adapters = adapters

    async def get_items(self) -> list[MyNewType]:
        try:
            results = await asyncio.gather(*(a.fetch() for a in self._adapters))
            return [item for batch in results for item in batch]
        except Exception as exc:
            log.warning("[my-domain] fetch failed: %s", exc)
            return []
```

**Step 4 — Singleton** (`services/{domain}/__init__.py`)

```python
from services.{domain}.adapters.source_x import SourceXAdapter
from services.{domain}.{Domain}Service import MyService

my_service = MyService(adapters=[SourceXAdapter()])
```

**Step 5 — Router** (`routers/{domain}.py`)

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from services.{domain} import my_service

router = APIRouter(tags=["{domain}"])

@router.get("/api/{domain}")
async def get_items() -> JSONResponse:
    items = await my_service.get_items()
    return JSONResponse(
        content=[i.model_dump(by_alias=True) for i in items],
        headers={"Cache-Control": "public, max-age=60"},
    )
```

Always use `model_dump(by_alias=True)`. No business logic in routers.

**Step 6 — Register** in `main.py`:

```python
from routers import my_new_router
app.include_router(my_new_router.router)
```

### Adding an adapter to an existing domain

1. Create `services/{domain}/adapters/{new_source}.py` implementing `I{Domain}Adapter`.
2. In `services/{domain}/__init__.py`, add it to `adapters=[...]`.

Nothing else changes.

### Caching TTL reference

| Refresh frequency | TTL |
|---|---|
| 30 s | `TTLCache(ttl_seconds=30)` |
| 60 s | `TTLCache(ttl_seconds=60)` |
| 5 min | `TTLCache(ttl_seconds=300)` |
| Snapshot proxy | `TTLCache(ttl_seconds=4, max_size=500)` |

### Settings

All env vars in `settings.py` with safe defaults:

```python
class Settings(BaseSettings):
    my_new_api_key: str = ""
```

Document in `.env.example`. Never hardcode credentials.

---

## 5. Frontend — `apps/web/`

### Directory structure

```
apps/web/src/
├── app/
│   ├── layout.tsx
│   └── page.tsx            # login gate → <WSR />
├── components/
│   ├── LoginPage.tsx        # green-on-black terminal login
│   ├── WSR.tsx              # root: GlobeEngine init + event wiring
│   └── ui/
│       ├── StatusBar.tsx
│       ├── DataLayerPanel.tsx
│       ├── IntelPanel.tsx
│       ├── IntelTicker.tsx
│       ├── CCTVPanel.tsx
│       └── GeoSearch.tsx
└── lib/
    ├── auth.ts              # sessionStorage login/logout/isAuthenticated
    ├── ontology.ts          # TypeScript BFO process type bindings
    ├── types.ts             # TypeScript mirror of apps/api/ports/models.py
    ├── shaders.ts           # post-processing shader definitions
    └── globe/
        ├── GlobeEngine.ts
        ├── GlobeLayerBase.ts
        ├── ports/
        │   ├── IGlobeLayerPort.ts
        │   ├── IDataSourcePort.ts
        │   └── ICesiumContextPort.ts
        └── adapters/
            ├── layers/
            └── data/
```

### API calls

All `/api/*` calls are proxied by `next.config.ts` to `apps/api` (default `http://localhost:8001`). Do not hardcode a full URL in data sources — use:

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';
```

With `API_BASE = ''`, requests go to the same origin and are caught by the Next.js proxy. Set `NEXT_PUBLIC_API_BASE_URL` only for non-local deployments.

### Adding a new data layer

**Step 1 — TypeScript type** (`lib/types.ts`)

Mirror the Pydantic DTO from `apps/api/ports/models.py` exactly, matching field aliases.

**Step 2 — Data source adapter** (`lib/globe/adapters/data/{Domain}DataSource.ts`)

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';

export class MyNewDataSource implements IDataSourcePort<MyNewType[]> {
  readonly dataSourceId = 'my-new-source';
  readonly targetLayerIds = ['my-new-layer'];
  readonly refreshIntervalMs = 60_000;
  private _last: MyNewType[] = [];

  async fetch(): Promise<DataSourceResult<MyNewType[]>> {
    const res = await fetch(`${API_BASE}/api/my-domain`);
    if (!res.ok) throw new Error(`my-domain ${res.status}`);
    const data: MyNewType[] = await res.json();
    const changed = JSON.stringify(data) !== JSON.stringify(this._last);
    this._last = data;
    return { data, changed, fetchedAt: Date.now() };
  }
}
```

**Step 3 — Layer adapter** (`lib/globe/adapters/layers/{Domain}LayerAdapter.ts`)

```typescript
export class MyNewLayerAdapter extends GlobeLayerBase<MyNewType[]> {
  readonly layerId = 'my-new-layer';
  readonly processType = 'wsr:MyNewProcess'; // must exist in ontology.ts

  private _primitives: Cesium.PrimitiveCollection | null = null;
  private _last: MyNewType[] = [];

  async initialize(): Promise<void> { /* create primitive collection */ }

  update(items: MyNewType[]): void {
    this._last = items;
    this._render();
  }

  setVisible(visible: boolean): void {
    this._visible = visible;
    if (this._primitives) this._primitives.show = visible;
    if (visible) this._render();
  }

  teardown(): void { this._primitives?.removeAll(); }

  private _render(): void {
    if (!this._primitives || !this._visible) return;
    this._primitives.removeAll();
    // build billboards, emit data:updated
    this.emit({ type: 'data:updated', layerId: this.layerId,
                payload: { count: this._last.length }, timestamp: Date.now() });
  }
}
```

**Step 4 — Register in `WSR.tsx`**

```tsx
engine
  .registerLayer(new MyNewLayerAdapter())
  .registerDataSource(new MyNewDataSource());
```

**Step 5 — Add toggle to `DataLayerPanel.tsx`**

```tsx
{ id: 'my-new-layer', label: 'My New Layer', icon: '◎', countKey: 'myNewCount' }
```

### Layer adapter rules

- Cache `_last` and re-render on `setVisible(true)` — prevents blank layers on toggle.
- Always emit `data:updated` with `{ count }` so UI badges update.
- Embed the full domain object in billboard `id: { _wv: true, _type: 'x', ...item }` for click handlers.
- `primitives.removeAll()` then rebuild on each `update()` — diffing Cesium primitives is fragile.

---

## 6. Cross-cutting conventions

### Units and field names

| Measurement | Unit | Field name |
|---|---|---|
| Latitude | WGS84 decimal degrees | `lat` |
| Longitude | WGS84 decimal degrees | `lon` |
| Altitude | metres ASL | `altitude` |
| Speed | m/s | `velocity` |
| Heading | degrees true, 0-360 | `heading` |
| Time | Unix epoch milliseconds | `time`, `pubDate` |
| Depth | km | `depth` |

### Naming conventions

| Thing | Convention | Example |
|---|---|---|
| Backend service folder | snake_case | `services/cctv/` |
| Backend service class | PascalCase | `CCTVService` |
| Backend adapter class | `{Source}Adapter` | `LondonAdapter` |
| Backend port interface | `I{X}Adapter`, `I{X}Service` | `ICCTVAdapter` |
| Frontend layer adapter | `{Domain}LayerAdapter` | `FlightLayerAdapter` |
| Frontend data source | `{Domain}DataSource` | `FlightDataSource` |
| Frontend layer ID | kebab-case, `-layer` suffix | `'flight-layer'` |
| Frontend data source ID | kebab-case, `-source` suffix | `'flight-source'` |

### Error handling

- **Backend adapters**: catch, log `log.warning("[domain] %s", exc)`, return `[]`.
- **Backend routers**: no try/except — services guarantee a valid return.
- **Frontend data sources**: let `fetch()` throw; `GlobeEngine` catches and logs.
- **Frontend layer adapters**: never throw in `update()` or `initialize()`.

### HTTP headers

Every backend adapter must send:

```python
_HEADERS = {"User-Agent": "WSR-Intel/1.0"}
```

ADSB.lol, OpenSky, and TfL return 403/429 without a User-Agent.

---

## 7. What NOT to do

| Anti-pattern | Why it breaks |
|---|---|
| Hand-editing `apps/api/ports/domain.py` | `make generate` overwrites it |
| Business logic in a router | Routers are HTTP skin only |
| Importing a service from another service domain | Circular dependency chains |
| Module-level `cache = {}` in an adapter | Race conditions; not cleared on hot reload |
| Creating a new `httpx.AsyncClient` in an adapter | Leaks connections; use `get_client()` |
| `disableDepthTestDistance: POSITIVE_INFINITY` on billboards | Renders visible from the other side of the globe |
| Not caching `_last` in a layer adapter | Layer goes blank on toggle |
| Missing `key` prop on panels that switch entity | React won't reset state when entity changes |
| Missing `model_dump(by_alias=True)` in a router | JSON aliases lost; frontend receives wrong field names |
| New fields in `models.py` without TTL update | Ontology no longer reflects reality |

---

## 8. Pre-submit checklist

**New data domain (end-to-end)**

- [ ] Added class(es) and properties to `ontology/wsr.ttl`
- [ ] Ran `make generate` from `apps/` — `apps/api/ports/domain.py` updated
- [ ] Added DTO to `apps/api/ports/models.py` with aliases and BFO comment
- [ ] Created `services/{domain}/{Domain}Port.py`
- [ ] Created `services/{domain}/{Domain}Service.py`
- [ ] Created `services/{domain}/adapters/{source}.py`
- [ ] Created `services/{domain}/__init__.py` with singleton
- [ ] Created `routers/{domain}.py` importing only the singleton
- [ ] Registered router in `apps/api/main.py`
- [ ] Added TypeScript type to `apps/web/src/lib/types.ts`
- [ ] Created `{Domain}DataSource.ts`
- [ ] Created `{Domain}LayerAdapter.ts` (emits `data:updated`)
- [ ] Registered both in `WSR.tsx`
- [ ] Added toggle + count badge in `DataLayerPanel.tsx`
- [ ] Added env vars to `settings.py` and `.env.example`

**New adapter for existing domain**

- [ ] Extended TTL if new fields needed, ran `make generate`
- [ ] Created `services/{domain}/adapters/{new_source}.py`
- [ ] Added to `adapters=[...]` in `services/{domain}/__init__.py`

**Bug fix**

- [ ] Root cause identified at the correct layer
- [ ] Fix contained within one layer — no logic leaking across boundaries
- [ ] No new module-level mutable state introduced
- [ ] If Cesium-related: `_visible` flag respected, `_last` cached, primitives rebuilt on `setVisible(true)`

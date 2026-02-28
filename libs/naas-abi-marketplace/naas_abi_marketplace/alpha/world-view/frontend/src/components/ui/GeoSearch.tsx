'use client';
import { useState, useRef, useCallback, useEffect } from 'react';

export interface GeoResult {
  displayName: string;
  shortName: string;
  country: string;
  type: string;
  lat: number;
  lon: number;
  boundingBox?: [number, number, number, number]; // minLat, maxLat, minLon, maxLon
}

interface GeoSearchProps {
  onSelect: (result: GeoResult) => void;
}

// Compute a sensible flight altitude from the bounding box size
function altitudeFromBbox(bbox?: [number, number, number, number]): number {
  if (!bbox) return 200000;
  const latSpan = Math.abs(bbox[1] - bbox[0]);
  const lonSpan = Math.abs(bbox[3] - bbox[2]);
  const span = Math.max(latSpan, lonSpan);
  // ~111km per degree; add padding and scale for a good overhead view
  const meters = span * 111000 * 2.5;
  return Math.max(800, Math.min(meters, 18000000));
}

const TYPE_ICON: Record<string, string> = {
  city: '◉',
  town: '◎',
  village: '○',
  country: '⬡',
  state: '◈',
  administrative: '◈',
  airport: '✈',
  aeroway: '✈',
  natural: '▲',
  peak: '▲',
  water: '≋',
  lake: '≋',
  river: '≋',
  island: '◑',
  region: '◈',
  suburb: '◎',
  quarter: '◎',
  neighbourhood: '◎',
  road: '—',
  railway: '⊟',
  building: '▪',
};

function typeIcon(type: string): string {
  return TYPE_ICON[type] ?? '◦';
}

// Quick suggestions shown before user types
const QUICK_LINKS: GeoResult[] = [
  // boundingBox drives altitude. For orbit we use a very small bbox so the formula
  // yields exactly ~18Mm — the camera formula then clamps pitch to -90° (nadir).
  { displayName: 'Global Orbit', shortName: 'Global Orbit', country: '', type: 'orbit', lat: 15, lon: 0, boundingBox: [-80, 80, -80, 80] },
  { displayName: 'New York City, USA', shortName: 'New York City', country: 'USA', type: 'city', lat: 40.7128, lon: -74.006, boundingBox: [40.5, 40.9, -74.3, -73.7] },
  { displayName: 'London, UK', shortName: 'London', country: 'UK', type: 'city', lat: 51.5074, lon: -0.1278, boundingBox: [51.28, 51.69, -0.51, 0.33] },
  { displayName: 'Dubai, UAE', shortName: 'Dubai', country: 'UAE', type: 'city', lat: 25.2048, lon: 55.2708, boundingBox: [24.8, 25.4, 54.9, 55.6] },
  { displayName: 'Tokyo, Japan', shortName: 'Tokyo', country: 'Japan', type: 'city', lat: 35.6762, lon: 139.6503, boundingBox: [35.5, 35.9, 139.4, 139.9] },
  { displayName: 'Washington DC, USA', shortName: 'Washington DC', country: 'USA', type: 'city', lat: 38.9072, lon: -77.0369, boundingBox: [38.79, 39.0, -77.12, -76.9] },
  { displayName: 'Paris, France', shortName: 'Paris', country: 'France', type: 'city', lat: 48.8566, lon: 2.3522, boundingBox: [48.81, 48.9, 2.22, 2.47] },
  { displayName: 'Beijing, China', shortName: 'Beijing', country: 'China', type: 'city', lat: 39.9042, lon: 116.4074, boundingBox: [39.6, 40.2, 116.0, 116.8] },
  { displayName: 'Moscow, Russia', shortName: 'Moscow', country: 'Russia', type: 'city', lat: 55.7558, lon: 37.6176, boundingBox: [55.49, 56.0, 37.32, 37.91] },
  { displayName: 'Sydney, Australia', shortName: 'Sydney', country: 'Australia', type: 'city', lat: -33.8688, lon: 151.2093, boundingBox: [-34.17, -33.58, 150.65, 151.63] },
];

export default function GeoSearch({ onSelect }: GeoSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GeoResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); setLoading(false); return; }
    setLoading(true);
    try {
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=8&addressdetails=1&extratags=0`;
      const res = await fetch(url, { headers: { 'Accept-Language': 'en', 'User-Agent': 'WorldView/1.0' } });
      if (!res.ok) return;
      const data = await res.json() as Array<{
        display_name: string;
        name?: string;
        type?: string;
        class?: string;
        lat: string;
        lon: string;
        boundingbox?: string[];
        address?: { country?: string; city?: string; town?: string; state?: string };
      }>;

      const mapped: GeoResult[] = data.map((item) => {
        const parts = item.display_name.split(',');
        const shortName = (item.name || parts[0] || '').trim();
        const country = item.address?.country ?? (parts[parts.length - 1] ?? '').trim();
        const bbox = item.boundingbox
          ? [parseFloat(item.boundingbox[0]), parseFloat(item.boundingbox[1]),
             parseFloat(item.boundingbox[2]), parseFloat(item.boundingbox[3])] as [number,number,number,number]
          : undefined;
        return {
          displayName: item.display_name,
          shortName,
          country,
          type: item.type ?? item.class ?? 'place',
          lat: parseFloat(item.lat),
          lon: parseFloat(item.lon),
          boundingBox: bbox,
        };
      });
      setResults(mapped);
    } catch { /* silent */ } finally {
      setLoading(false);
    }
  }, []);

  const handleInput = (val: string) => {
    setQuery(val);
    setActiveIdx(-1);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!val.trim()) { setResults([]); return; }
    debounceRef.current = setTimeout(() => search(val), 320);
  };

  const handleSelect = (r: GeoResult) => {
    setQuery(r.shortName);
    setResults([]);
    setOpen(false);
    setActiveIdx(-1);
    onSelect(r);
    inputRef.current?.blur();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const list = query.trim() ? results : QUICK_LINKS;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx((i) => Math.min(i + 1, list.length - 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setActiveIdx((i) => Math.max(i - 1, -1)); }
    if (e.key === 'Enter') {
      if (activeIdx >= 0 && list[activeIdx]) { handleSelect(list[activeIdx]); }
      else if (query.trim()) search(query);
    }
    if (e.key === 'Escape') { setOpen(false); inputRef.current?.blur(); }
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const displayList = query.trim() ? results : QUICK_LINKS;
  const showDropdown = open && displayList.length > 0;

  return (
    <div ref={containerRef} className="relative font-mono" style={{ width: 420 }}>
      {/* Search input */}
      <div
        className="flex items-center gap-2 px-3 py-2 border border-green-500/30 transition-all"
        style={{
          background: 'rgba(0,0,0,0.92)',
          backdropFilter: 'blur(8px)',
          borderColor: open ? 'rgba(0,255,65,0.6)' : 'rgba(0,255,65,0.25)',
          boxShadow: open ? '0 0 12px rgba(0,255,65,0.1)' : 'none',
        }}
      >
        {/* Search icon */}
        <span className="text-green-500/50 text-xs select-none shrink-0">
          {loading ? (
            <span className="animate-spin inline-block">◌</span>
          ) : (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <circle cx="5" cy="5" r="3.5" stroke="currentColor" strokeWidth="1.2"/>
              <line x1="7.8" y1="7.8" x2="11" y2="11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
          )}
        </span>

        <input
          ref={inputRef}
          type="text"
          value={query}
          placeholder="SEARCH ANY PLACE ON EARTH..."
          onChange={(e) => handleInput(e.target.value)}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          className="flex-1 bg-transparent outline-none text-green-300 placeholder-green-500/30 text-[11px] tracking-wider uppercase"
          autoComplete="off"
          spellCheck={false}
        />

        {query && (
          <button
            onClick={() => { setQuery(''); setResults([]); setActiveIdx(-1); inputRef.current?.focus(); }}
            className="text-green-500/30 hover:text-green-400/60 text-xs shrink-0 px-0.5"
          >
            ✕
          </button>
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div
          className="absolute top-full left-0 right-0 z-50 border border-green-500/20 border-t-0 overflow-hidden"
          style={{ background: 'rgba(0,4,0,0.97)', backdropFilter: 'blur(12px)', maxHeight: 320 }}
        >
          {!query.trim() && (
            <div className="px-3 py-1.5 border-b border-green-500/10 flex items-center gap-2">
              <span className="text-[9px] text-green-500/30 tracking-widest uppercase">Quick Navigation</span>
            </div>
          )}

          <div className="overflow-y-auto" style={{ maxHeight: query.trim() ? 320 : 290 }}>
            {displayList.map((r, i) => (
              <button
                key={`${r.lat}-${r.lon}-${i}`}
                onMouseDown={(e) => { e.preventDefault(); handleSelect(r); }}
                onMouseEnter={() => setActiveIdx(i)}
                className="w-full flex items-center gap-3 px-3 py-2 text-left transition-all border-b border-green-500/5 last:border-0"
                style={{
                  background: i === activeIdx ? 'rgba(0,255,65,0.06)' : 'transparent',
                  borderLeft: i === activeIdx ? '2px solid rgba(0,255,65,0.5)' : '2px solid transparent',
                }}
              >
                {/* Type icon */}
                <span className="text-green-400/50 text-sm w-4 shrink-0 text-center">{typeIcon(r.type)}</span>

                {/* Name + country */}
                <div className="flex-1 min-w-0">
                  <div className="text-green-300 text-[11px] tracking-wider truncate">{r.shortName}</div>
                  {r.country && (
                    <div className="text-green-500/40 text-[9px] tracking-wider truncate">{r.country}</div>
                  )}
                </div>

                {/* Coordinates */}
                <div className="text-green-500/30 text-[9px] tracking-wider shrink-0 text-right">
                  <div>{r.lat.toFixed(2)}°</div>
                  <div>{r.lon.toFixed(2)}°</div>
                </div>
              </button>
            ))}
          </div>

          {query.trim() && results.length === 0 && !loading && (
            <div className="px-3 py-3 text-[10px] text-green-500/30 tracking-wider text-center">
              NO RESULTS — TRY A DIFFERENT QUERY
            </div>
          )}

          <div className="px-3 py-1 border-t border-green-500/10 flex items-center justify-between">
            <span className="text-[8px] text-green-500/20 tracking-widest">DATA: OPENSTREETMAP / NOMINATIM</span>
            <span className="text-[8px] text-green-500/20">↑↓ NAVIGATE · ENTER SELECT · ESC CLOSE</span>
          </div>
        </div>
      )}
    </div>
  );
}

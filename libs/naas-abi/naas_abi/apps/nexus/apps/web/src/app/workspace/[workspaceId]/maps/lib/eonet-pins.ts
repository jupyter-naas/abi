import type { MapsPinMarker } from './leaflet-map';

const CATEGORY_COLORS: Record<string, string> = {
  wildfires: '#dc2626',
  volcanoes: '#7c3aed',
  severeStorms: '#2563eb',
  floods: '#0ea5e9',
  earthquakes: '#ea580c',
  landslides: '#a16207',
  drought: '#ca8a04',
  dustHaze: '#78716c',
  snow: '#38bdf8',
  tempExtremes: '#f97316',
  waterColor: '#06b6d4',
  seaLakeIce: '#67e8f9',
  manmade: '#64748b',
};

interface EonetEvent {
  id?: string;
  title?: string;
  categories?: Array<{ id?: string; title?: string }>;
  geometry?: Array<{
    date?: string;
    type?: string;
    coordinates?: number[] | number[][];
  }>;
}

export function eonetEventsToPins(
  events: EonetEvent[],
  opts?: { color?: string },
): MapsPinMarker[] {
  const pins: MapsPinMarker[] = [];
  for (const event of events) {
    const geoms = event.geometry ?? [];
    const point = [...geoms].reverse().find((g) => g.type === 'Point');
    const coords = point?.coordinates;
    if (!coords || !Array.isArray(coords) || typeof coords[0] !== 'number') {
      continue;
    }
    const [lng, lat] = coords as number[];
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    const catId = event.categories?.[0]?.id ?? 'event';
    const catTitle = event.categories?.[0]?.title ?? catId;
    const when = point?.date
      ? new Date(point.date).toLocaleString(undefined, {
          dateStyle: 'medium',
          timeStyle: 'short',
        })
      : null;
    pins.push({
      id: String(event.id ?? `${lat},${lng}`),
      lat,
      lng,
      label: event.title ?? catTitle,
      detail: [catTitle, when].filter(Boolean).join(' · '),
      color: opts?.color ?? CATEGORY_COLORS[catId] ?? '#2563eb',
    });
  }
  return pins;
}

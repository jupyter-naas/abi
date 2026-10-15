/** GDACS multi-hazard events (GeoJSON MAP endpoint), one event type per call. */

export const GDACS_EVENT_TYPES = ['EQ', 'TC', 'FL', 'VO', 'DR', 'WF'] as const;

export const GDACS_PIN_LIMIT = 300;

const EVENT_COLORS: Record<string, string> = {
  EQ: '#ea580c',
  TC: '#2563eb',
  FL: '#0ea5e9',
  VO: '#7c3aed',
  DR: '#ca8a04',
  WF: '#dc2626',
};

export type GdacsCollection = {
  features?: Array<{
    properties?: {
      eventtype?: string;
      eventid?: number | string;
      name?: string;
      description?: string;
      alertlevel?: string;
    };
    geometry?: { type?: string; coordinates?: number[] };
  }>;
};

/** The endpoint refuses a call without one `eventtype` ("Eventtype is required."). */
export function gdacsEventUrl(eventType: string): string {
  return `https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP?eventtype=${encodeURIComponent(eventType)}`;
}

/** Pins of every collection, each event once, at most `limit`. */
export function collectGdacsPins(
  collections: GdacsCollection[],
  limit: number = GDACS_PIN_LIMIT,
): Array<Record<string, unknown>> {
  const pins: Array<Record<string, unknown>> = [];
  const seen = new Set<string>();
  for (const data of collections) {
    for (const f of data.features ?? []) {
      if (pins.length >= limit) return pins;
      const coords = f.geometry?.coordinates;
      if (!coords || coords.length < 2) continue;
      const [lng, lat] = coords;
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
      const p = f.properties ?? {};
      const et = p.eventtype ?? 'HZ';
      const id = `${et}-${p.eventid ?? `${lat},${lng}`}`;
      if (seen.has(id)) continue;
      seen.add(id);
      pins.push({
        id,
        lat,
        lng,
        label: p.name || p.description || `${et} event`,
        detail: `${et}${p.alertlevel ? ` · ${p.alertlevel}` : ''} · GDACS`,
        color: EVENT_COLORS[et] ?? '#64748b',
        size: 10,
      });
    }
  }
  return pins;
}

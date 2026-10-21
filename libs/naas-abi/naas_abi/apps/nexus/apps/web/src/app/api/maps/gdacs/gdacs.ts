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

type Feature = NonNullable<GdacsCollection['features']>[number];

function pinOf(f: Feature): Record<string, unknown> | null {
  const coords = f.geometry?.coordinates;
  if (!coords || coords.length < 2) return null;
  const [lng, lat] = coords;
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  const p = f.properties ?? {};
  const et = p.eventtype ?? 'HZ';
  return {
    id: `${et}-${p.eventid ?? `${lat},${lng}`}`,
    lat,
    lng,
    label: p.name || p.description || `${et} event`,
    detail: `${et}${p.alertlevel ? ` · ${p.alertlevel}` : ''} · GDACS`,
    color: EVENT_COLORS[et] ?? '#64748b',
    size: 10,
  };
}

/**
 * Pins of every collection, each event once, at most `limit`. The collections
 * take turns (one event of each in turn), so a long list of earthquakes does
 * not crowd out the cyclones and floods that come after it.
 */
export function collectGdacsPins(
  collections: GdacsCollection[],
  limit: number = GDACS_PIN_LIMIT,
): Array<Record<string, unknown>> {
  const pins: Array<Record<string, unknown>> = [];
  const seen = new Set<string>();
  const next = collections.map(() => 0);
  let progressed = true;
  while (progressed && pins.length < limit) {
    progressed = false;
    for (let c = 0; c < collections.length && pins.length < limit; c++) {
      const features = collections[c].features ?? [];
      while (next[c] < features.length) {
        const pin = pinOf(features[next[c]++]);
        if (!pin || seen.has(pin.id as string)) continue;
        seen.add(pin.id as string);
        pins.push(pin);
        progressed = true;
        break;
      }
    }
  }
  return pins;
}

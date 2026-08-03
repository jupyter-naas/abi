import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const EVENT_COLORS: Record<string, string> = {
  EQ: '#ea580c',
  TC: '#2563eb',
  FL: '#0ea5e9',
  VO: '#7c3aed',
  DR: '#ca8a04',
  WF: '#dc2626',
};

/** GDACS multi-hazard event list (GeoJSON MAP endpoint). */
export async function GET() {
  try {
    const res = await mapsUpstreamGet(
      'https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP',
      { timeoutMs: 25000 },
    );
    if (!res.ok) {
      return mapsJson(
        { error: `GDACS ${res.status}`, pins: [], count: 0 },
        { status: 502 },
      );
    }
    const data = (await res.json()) as {
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
    const pins: Array<Record<string, unknown>> = [];
    for (const f of data.features ?? []) {
      const coords = f.geometry?.coordinates;
      if (!coords || coords.length < 2) continue;
      const [lng, lat] = coords;
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
      const p = f.properties ?? {};
      const et = p.eventtype ?? 'HZ';
      pins.push({
        id: String(p.eventid ?? `${lat},${lng}`),
        lat,
        lng,
        label: p.name || p.description || `${et} event`,
        detail: `${et}${p.alertlevel ? ` · ${p.alertlevel}` : ''} · GDACS`,
        color: EVENT_COLORS[et] ?? '#64748b',
        size: 10,
      });
      if (pins.length >= 300) break;
    }
    return mapsJson({ pins, count: pins.length, source: 'gdacs.org' });
  } catch (err) {
    return mapsJson(
      {
        error: err instanceof Error ? err.message : 'GDACS fetch failed',
        pins: [],
        count: 0,
      },
      { status: 502 },
    );
  }
}

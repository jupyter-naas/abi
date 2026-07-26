import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * OpenAQ v3 locations (requires OPENAQ_API_KEY).
 * Without a key, returns an honest empty state so the Maps canvas can explain it.
 */
export async function GET() {
  const apiKey = process.env.OPENAQ_API_KEY?.trim();
  if (!apiKey) {
    return mapsJson({
      pins: [],
      count: 0,
      empty: true,
      reason:
        'OpenAQ v3 requires a free API key. Set OPENAQ_API_KEY on the Nexus web host to enable this layer.',
      source: 'openaq.org',
    });
  }

  try {
    const res = await mapsUpstreamGet(
      'https://api.openaq.org/v3/locations?limit=100&sort=lastUpdated&order_by=desc',
      {
        timeoutMs: 20000,
        headers: { 'X-API-Key': apiKey },
      },
    );
    if (!res.ok) {
      return mapsJson(
        {
          error: `OpenAQ ${res.status}`,
          pins: [],
          count: 0,
          empty: true,
          reason: `OpenAQ returned HTTP ${res.status}`,
        },
        { status: 502 },
      );
    }
    const data = (await res.json()) as {
      results?: Array<{
        id?: number | string;
        name?: string;
        locality?: string;
        country?: { name?: string; code?: string };
        coordinates?: { latitude?: number; longitude?: number };
      }>;
    };
    const pins: Array<Record<string, unknown>> = [];
    for (const loc of data.results ?? []) {
      const lat = loc.coordinates?.latitude;
      const lng = loc.coordinates?.longitude;
      if (lat == null || lng == null) continue;
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
      pins.push({
        id: String(loc.id ?? `${lat},${lng}`),
        lat,
        lng,
        label: loc.name || loc.locality || 'OpenAQ station',
        detail: `${loc.country?.name ?? loc.country?.code ?? 'Unknown'} · OpenAQ`,
        color: '#059669',
        size: 8,
      });
    }
    return mapsJson({
      pins,
      count: pins.length,
      empty: pins.length === 0,
      source: 'openaq.org',
    });
  } catch (err) {
    return mapsJson(
      {
        error: err instanceof Error ? err.message : 'OpenAQ fetch failed',
        pins: [],
        count: 0,
        empty: true,
        reason: 'OpenAQ request failed',
      },
      { status: 502 },
    );
  }
}

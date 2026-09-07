import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * Air quality samples.
 * Prefers OpenAQ when OPENAQ_API_KEY is set; otherwise Open-Meteo PM2.5 city
 * samples so the Public layer still ships a working canvas.
 */
const OPEN_METEO_CITIES: Array<{ lat: number; lng: number; label: string }> = [
  { lat: 40.71, lng: -74.01, label: 'New York' },
  { lat: 34.05, lng: -118.24, label: 'Los Angeles' },
  { lat: 51.51, lng: -0.13, label: 'London' },
  { lat: 48.86, lng: 2.35, label: 'Paris' },
  { lat: 52.52, lng: 13.4, label: 'Berlin' },
  { lat: 35.68, lng: 139.69, label: 'Tokyo' },
  { lat: 28.61, lng: 77.21, label: 'Delhi' },
  { lat: 19.43, lng: -99.13, label: 'Mexico City' },
  { lat: -23.55, lng: -46.63, label: 'Sao Paulo' },
  { lat: 30.04, lng: 31.24, label: 'Cairo' },
  { lat: 1.35, lng: 103.82, label: 'Singapore' },
  { lat: -33.87, lng: 151.21, label: 'Sydney' },
  { lat: 39.9, lng: 116.4, label: 'Beijing' },
  { lat: 6.52, lng: 3.38, label: 'Lagos' },
  { lat: 41.01, lng: 28.98, label: 'Istanbul' },
];

function pmColor(pm25: number): string {
  if (pm25 <= 12) return '#16a34a';
  if (pm25 <= 35) return '#ca8a04';
  if (pm25 <= 55) return '#ea580c';
  return '#dc2626';
}

export async function GET() {
  const apiKey = process.env.OPENAQ_API_KEY?.trim();

  if (apiKey) {
    try {
      const res = await mapsUpstreamGet(
        'https://api.openaq.org/v3/locations?limit=100&sort=lastUpdated&order_by=desc',
        {
          timeoutMs: 20000,
          headers: { 'X-API-Key': apiKey },
        },
      );
      if (res.ok) {
        const data = (await res.json()) as {
          results?: Array<{
            id?: number | string;
            name?: string;
            locality?: string;
            country?: { name?: string; code?: string };
            coordinates?: { latitude?: number; longitude?: number };
          }>;
        };
        const pins = [];
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
        if (pins.length > 0) {
          return mapsJson(
            { pins, count: pins.length, source: 'openaq' },
            { cacheSeconds: 300 },
          );
        }
      }
    } catch {
      // fall through to Open-Meteo
    }
  }

  const pins = await fetchOpenMeteo();
  return mapsJson(
    {
      pins,
      count: pins.length,
      source: 'open-meteo',
      note: apiKey
        ? 'OpenAQ empty or failed; showing Open-Meteo PM2.5 city samples.'
        : 'OPENAQ_API_KEY unset; showing Open-Meteo PM2.5 city samples.',
    },
    { cacheSeconds: 300 },
  );
}

async function fetchOpenMeteo() {
  const pins: Array<{
    id: string;
    lat: number;
    lng: number;
    label: string;
    detail: string;
    color: string;
  }> = [];
  await Promise.all(
    OPEN_METEO_CITIES.map(async (city) => {
      try {
        const url = `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${city.lat}&longitude=${city.lng}&current=pm2_5`;
        const res = await mapsUpstreamGet(url, { timeoutMs: 10000 });
        if (!res.ok) return;
        const data = (await res.json()) as {
          current?: { pm2_5?: number };
        };
        const pm25 = data.current?.pm2_5;
        if (typeof pm25 !== 'number') return;
        pins.push({
          id: city.label,
          lat: city.lat,
          lng: city.lng,
          label: city.label,
          detail: `PM2.5 ${pm25.toFixed(1)} µg/m³ · Open-Meteo`,
          color: pmColor(pm25),
        });
      } catch {
        // skip city
      }
    }),
  );
  return pins;
}

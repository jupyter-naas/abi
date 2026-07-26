import { mapsJson } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * AIS ships. Free aisstream / MarineTraffic tiers need a registered key.
 * Dataset stays registered with an honest empty state until a key is set.
 */
export async function GET() {
  const apiKey =
    process.env.AISSTREAM_API_KEY?.trim() ||
    process.env.AIS_API_KEY?.trim() ||
    '';

  if (!apiKey) {
    return mapsJson(
      {
        pins: [],
        count: 0,
        empty: true,
        needsKey: true,
        message:
          'AIS ships layer needs AISSTREAM_API_KEY (or AIS_API_KEY) on the nexus-web runtime. Dataset is registered; configure a free/paid AIS provider to populate pins.',
        reason:
          'No free keyless AIS feed is configured. Set AISSTREAM_API_KEY to enable.',
        docs: 'https://aisstream.io/',
        source: 'ais',
      },
      { cacheSeconds: 60 },
    );
  }

  return mapsJson(
    {
      pins: [],
      count: 0,
      empty: true,
      needsKey: true,
      message:
        'AIS HTTP snapshot not wired yet. WebSocket AIS providers (aisstream) need a bridge; key is present but pins are empty until that lands.',
      reason: 'AIS key present but HTTP bridge not implemented.',
      docs: 'https://aisstream.io/',
      source: 'ais',
    },
    { cacheSeconds: 60 },
  );
}

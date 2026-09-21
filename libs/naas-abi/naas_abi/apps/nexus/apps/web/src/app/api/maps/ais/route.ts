import { mapsJson } from '../_lib';
import {
  AIS_PIN_LIMIT,
  aisVesselsToPins,
  parseAisBounds,
  vesselsInView,
} from './store';
import { aisStreamApiKey, aisStreamSnapshot, ensureAisStream } from './stream';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * AIS ships. AISStream is a server-side WebSocket; the browser polls this snapshot.
 * The cache is process-local (next start / Docker nexus-web). Cloudflare Pages
 * isolates cannot hold the stream and will report that honestly.
 */
export async function GET(req: Request) {
  const key = aisStreamApiKey();
  if (!key) {
    return mapsJson(
      {
        pins: [],
        count: 0,
        empty: true,
        needsKey: true,
        source: 'aisstream',
        attribution: 'AISStream',
        status: 'missing-key',
        message:
          'AIS ships layer needs AISSTREAM_API_KEY on the nexus-web runtime. Dataset is registered; configure a free AISStream key to populate pins.',
        reason:
          'No free keyless AIS feed is configured. Set AISSTREAM_API_KEY to enable.',
        docs: 'https://aisstream.io/',
      },
      { cacheSeconds: 60 },
    );
  }

  ensureAisStream();
  const url = new URL(req.url);
  const bounds = parseAisBounds(url.searchParams);
  const snapshot = aisStreamSnapshot();
  const rows = vesselsInView(snapshot.vessels, bounds, AIS_PIN_LIMIT);
  const pins = aisVesselsToPins(rows);
  const observedAt = snapshot.lastMessageAt
    ? new Date(snapshot.lastMessageAt).toISOString()
    : undefined;
  const coverage = bounds ? 'viewport' : 'global-sample';
  const connecting = snapshot.status === 'connecting' || snapshot.status === 'unavailable';
  const empty = pins.length === 0;

  let message: string | undefined;
  if (snapshot.status === 'unavailable') {
    message = snapshot.error ?? undefined;
  } else if (snapshot.status === 'auth-failed') {
    message =
      'AISStream rejected the API key. Check AISSTREAM_API_KEY on nexus-web.';
  } else if (snapshot.status === 'connecting' && empty) {
    message =
      'AISStream is connecting. Keep this Maps server process running; the cache fills as position reports arrive.';
  } else if (snapshot.status === 'error' && empty) {
    message = snapshot.error ?? 'AISStream is down. Retrying in the background.';
  } else if (empty && bounds) {
    message = 'No vessels in this view. Pan or zoom to another area.';
  } else if (empty) {
    message = 'AISStream has not delivered a position report yet.';
  }

  return mapsJson(
    {
      pins,
      count: pins.length,
      empty,
      source: 'aisstream',
      attribution: 'AISStream',
      status: snapshot.status,
      coverage,
      observedAt,
      stale: snapshot.status !== 'live',
      message,
      reason: message,
      docs: 'https://aisstream.io/',
    },
    { cacheSeconds: 0 },
  );
}

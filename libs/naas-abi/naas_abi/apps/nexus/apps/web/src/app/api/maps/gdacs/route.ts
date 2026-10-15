import { mapsPinResponse, mapsUpstreamGet } from '../_lib';
import {
  collectGdacsPins,
  GDACS_EVENT_TYPES,
  gdacsEventUrl,
  type GdacsCollection,
} from './gdacs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

async function fetchEventType(eventType: string): Promise<GdacsCollection> {
  const res = await mapsUpstreamGet(gdacsEventUrl(eventType), { timeoutMs: 25000 });
  if (!res.ok) throw new Error(`GDACS ${eventType} ${res.status}`);
  return (await res.json()) as GdacsCollection;
}

/** GDACS multi-hazard event list: one call per event type, merged. A type that
 * fails is left out; the layer fails only when every type does. */
export async function GET() {
  const results = await Promise.allSettled(GDACS_EVENT_TYPES.map(fetchEventType));
  const collections: GdacsCollection[] = [];
  const failed: string[] = [];
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') collections.push(result.value);
    else failed.push(GDACS_EVENT_TYPES[index]);
  });
  if (!collections.length) {
    const first = results.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined;
    const reason = first?.reason;
    return mapsPinResponse(
      [],
      { error: reason instanceof Error ? reason.message : 'GDACS fetch failed' },
      { status: 502 },
    );
  }
  return mapsPinResponse(collectGdacsPins(collections), {
    source: 'gdacs.org',
    ...(failed.length ? { unavailable: failed } : {}),
  });
}

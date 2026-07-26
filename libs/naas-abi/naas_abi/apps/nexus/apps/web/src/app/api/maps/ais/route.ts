import { mapsJson } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * AIS vessel layer placeholder.
 * Free keyless AIS streams are not available for product use (AISStream / AISHub /
 * MarineTraffic require registration or paid plans). Register the layer with an
 * honest empty state until a free-or-licensed source is configured.
 */
export async function GET() {
  return mapsJson({
    pins: [],
    count: 0,
    empty: true,
    reason:
      'No free keyless AIS feed is configured. AISStream, AISHub, and MarineTraffic require registration or a paid plan. This Maps layer is reserved for a licensed source.',
    source: 'none',
  });
}

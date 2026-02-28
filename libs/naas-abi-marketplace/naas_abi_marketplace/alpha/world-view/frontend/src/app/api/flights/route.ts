import { NextResponse } from 'next/server';
import type { FlightState } from '@/lib/types';

let cache: { data: FlightState[]; at: number } | null = null;
const CACHE_TTL = 30 * 1000; // 30 seconds

export async function GET() {
  if (cache && Date.now() - cache.at < CACHE_TTL) {
    return NextResponse.json(cache.data);
  }

  try {
    const username = process.env.OPENSKY_USERNAME;
    const password = process.env.OPENSKY_PASSWORD;
    const auth = username && password
      ? `Basic ${Buffer.from(`${username}:${password}`).toString('base64')}`
      : undefined;

    const res = await fetch('https://opensky-network.org/api/states/all', {
      headers: {
        'User-Agent': 'WorldView/1.0',
        ...(auth ? { Authorization: auth } : {}),
      },
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) throw new Error(`OpenSky returned ${res.status}`);

    const json = await res.json();
    const states: FlightState[] = (json.states ?? [])
      .filter((s: unknown[]) => s[5] != null && s[6] != null)
      .map((s: unknown[]) => ({
        icao24: s[0] as string,
        callsign: ((s[1] as string) ?? '').trim() || (s[0] as string),
        lat: s[6] as number,
        lon: s[5] as number,
        altitude: (s[7] as number) ?? 0,
        velocity: (s[9] as number) ?? 0,
        heading: (s[10] as number) ?? 0,
        onGround: s[8] as boolean,
      }));

    cache = { data: states, at: Date.now() };
    return NextResponse.json(states);
  } catch (err) {
    console.error('[flights]', err);
    return NextResponse.json(cache?.data ?? []);
  }
}

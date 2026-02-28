import { NextResponse } from 'next/server';
import type { FlightState } from '@/lib/types';

let cache: { data: FlightState[]; at: number } | null = null;
const CACHE_TTL = 60 * 1000; // 60 seconds

export async function GET() {
  if (cache && Date.now() - cache.at < CACHE_TTL) {
    return NextResponse.json(cache.data);
  }

  try {
    const res = await fetch('https://api.adsb.lol/v2/mil', {
      headers: { 'User-Agent': 'WorldView/1.0' },
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) throw new Error(`ADSB.lol returned ${res.status}`);

    const json = await res.json();
    const aircraft = json.ac ?? [];

    const states: FlightState[] = aircraft
      .filter((a: Record<string, unknown>) => a.lat != null && a.lon != null)
      .map((a: Record<string, unknown>) => ({
        icao24: (a.hex as string) ?? '',
        callsign: ((a.flight as string) ?? '').trim() || ((a.hex as string) ?? ''),
        lat: a.lat as number,
        lon: a.lon as number,
        altitude: ((a.alt_baro as number) ?? 0) * 0.3048, // ft to m
        velocity: ((a.gs as number) ?? 0) * 0.514444, // knots to m/s
        heading: (a.track as number) ?? 0,
        onGround: false,
        isMilitary: true,
      }));

    cache = { data: states, at: Date.now() };
    return NextResponse.json(states);
  } catch (err) {
    console.error('[military]', err);
    return NextResponse.json(cache?.data ?? []);
  }
}

import { NextResponse } from 'next/server';
import type { EarthquakeFeature } from '@/lib/types';

let cache: { data: EarthquakeFeature[]; at: number } | null = null;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export async function GET() {
  if (cache && Date.now() - cache.at < CACHE_TTL) {
    return NextResponse.json(cache.data);
  }

  try {
    const res = await fetch(
      'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson',
      { headers: { 'User-Agent': 'WorldView/1.0' }, signal: AbortSignal.timeout(8000) }
    );

    if (!res.ok) throw new Error(`USGS returned ${res.status}`);

    const geojson = await res.json();
    const quakes: EarthquakeFeature[] = geojson.features
      .filter((f: { properties: { mag: number } }) => f.properties.mag >= 1.0)
      .map((f: { id: string; properties: Record<string, unknown>; geometry: { coordinates: number[] } }) => ({
        id: f.id,
        mag: f.properties.mag as number,
        place: f.properties.place as string,
        lat: f.geometry.coordinates[1],
        lon: f.geometry.coordinates[0],
        depth: f.geometry.coordinates[2],
        time: f.properties.time as number,
      }));

    cache = { data: quakes, at: Date.now() };
    return NextResponse.json(quakes);
  } catch (err) {
    console.error('[earthquakes]', err);
    return NextResponse.json(cache?.data ?? []);
  }
}

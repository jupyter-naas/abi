import { NextResponse } from 'next/server';
import type { CCTVCamera } from '@/lib/types';

let cache: { data: CCTVCamera[]; at: number } | null = null;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

const OPENWEBCAMDB_KEY = process.env.OPENWEBCAMDB_API_KEY ?? '';

// NYC area bounding box (Manhattan + surrounding boroughs)
const NYC_BOUNDS = { minLat: 40.60, maxLat: 40.90, minLon: -74.05, maxLon: -73.70 };

// London bounding box
const LON_BOUNDS = { minLat: 51.35, maxLat: 51.65, minLon: -0.50, maxLon: 0.20 };

async function fetchNYCCameras(): Promise<CCTVCamera[]> {
  try {
    const res = await fetch('https://511ny.org/api/getcameras?key=&format=json', {
      headers: { 'User-Agent': 'WorldView/1.0' },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return [];
    const data = await res.json() as Array<{
      ID: string; Name: string; Latitude: number; Longitude: number;
      VideoUrl?: string | null; Disabled?: boolean; Blocked?: boolean;
    }>;

    return data
      .filter((c) =>
        !c.Disabled && !c.Blocked &&
        c.VideoUrl &&
        c.Latitude >= NYC_BOUNDS.minLat && c.Latitude <= NYC_BOUNDS.maxLat &&
        c.Longitude >= NYC_BOUNDS.minLon && c.Longitude <= NYC_BOUNDS.maxLon
      )
      .map((c) => ({
        id: `nyc-${c.ID}`,
        name: c.Name,
        lat: c.Latitude,
        lon: c.Longitude,
        city: 'New York',
        country: 'USA',
        imageUrl: '',
        videoUrl: c.VideoUrl!,
        active: true,
        type: 'hls' as const,
        source: 'nyc' as const,
      }))
      .slice(0, 150);
  } catch {
    return [];
  }
}

async function fetchLondonCameras(): Promise<CCTVCamera[]> {
  try {
    const res = await fetch('https://api.tfl.gov.uk/Place/Type/JamCam', {
      headers: { 'User-Agent': 'WorldView/1.0' },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return [];
    const data = await res.json() as Array<{
      id: string; commonName: string; lat: number; lon: number;
      additionalProperties?: Array<{ key: string; value: string }>;
    }>;

    const cameras: CCTVCamera[] = [];
    for (const cam of data) {
      if (cam.lat < LON_BOUNDS.minLat || cam.lat > LON_BOUNDS.maxLat ||
          cam.lon < LON_BOUNDS.minLon || cam.lon > LON_BOUNDS.maxLon) continue;

      const props = cam.additionalProperties ?? [];
      const imgProp = props.find((p) => p.key === 'imageUrl');
      const vidProp = props.find((p) => p.key === 'videoUrl');
      if (!imgProp && !vidProp) continue;

      cameras.push({
        id: `lon-${cam.id}`,
        name: cam.commonName,
        lat: cam.lat,
        lon: cam.lon,
        city: 'London',
        country: 'UK',
        imageUrl: imgProp?.value ?? '',
        videoUrl: vidProp?.value ?? '',
        active: true,
        type: 'mp4' as const,
        source: 'london' as const,
      });
    }
    return cameras.slice(0, 150);
  } catch {
    return [];
  }
}

// Fetch global webcams from OpenWebcamDB (only when API key is set)
async function fetchOpenWebcamDB(): Promise<CCTVCamera[]> {
  if (!OPENWEBCAMDB_KEY) return [];
  try {
    // Call our own /api/webcams endpoint which handles caching + rate limiting
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_BASE_URL ?? 'http://localhost:3000'}/api/webcams`,
      { signal: AbortSignal.timeout(15000) }
    );
    if (!res.ok) return [];
    return (await res.json()) as CCTVCamera[];
  } catch {
    return [];
  }
}

export async function GET() {
  if (cache && Date.now() - cache.at < CACHE_TTL) {
    return NextResponse.json(cache.data);
  }

  const [nyc, london, global] = await Promise.all([
    fetchNYCCameras(),
    fetchLondonCameras(),
    fetchOpenWebcamDB(),
  ]);
  const cameras = [...nyc, ...london, ...global];
  cache = { data: cameras, at: Date.now() };

  return NextResponse.json(cameras, {
    headers: { 'Cache-Control': 'public, s-maxage=300' },
  });
}

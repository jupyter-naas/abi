import { NextResponse } from 'next/server';
import type { CCTVCamera } from '@/lib/types';

const API_KEY = process.env.OPENWEBCAMDB_API_KEY?.replace(/^"|"$/g, '') ?? '';
const BASE    = 'https://openwebcamdb.com/api/v1';

// Cache for 1 hour — maximum allowed by free tier ToS
let cache: { data: CCTVCamera[]; at: number } | null = null;
const CACHE_TTL = 60 * 60 * 1000;

interface WebcamListItem {
  slug: string;
  title: string;
  city: string | null;
  latitude: string;   // returned as string
  longitude: string;  // returned as string
  thumbnail_url?: string;
  stream_type?: string;
  country?: { name: string; iso_code: string };
}

interface WebcamListResponse {
  data: WebcamListItem[];
  meta?: { total?: number; last_page?: number };
}

async function fetchPage(page: number, perPage = 50): Promise<WebcamListItem[]> {
  const url = `${BASE}/webcams?per_page=${perPage}&page=${page}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'User-Agent': 'WorldView/1.0',
      Accept: 'application/json',
    },
    signal: AbortSignal.timeout(12000),
  });
  if (!res.ok) return [];
  const body = (await res.json()) as WebcamListResponse;
  return Array.isArray(body.data) ? body.data : [];
}

function toCamera(w: WebcamListItem): CCTVCamera | null {
  const lat = parseFloat(w.latitude);
  const lon = parseFloat(w.longitude);
  if (isNaN(lat) || isNaN(lon)) return null;

  return {
    id: `owdb-${w.slug}`,
    slug: w.slug,
    name: w.title,
    lat,
    lon,
    city: w.city ?? w.country?.name ?? 'Unknown',
    country: w.country?.name,
    imageUrl: w.thumbnail_url ?? '',
    videoUrl: '',              // fetched on-demand via /api/webcams/stream?slug=...
    type: 'youtube' as const, // both 'youtube' and 'iframe' render as <iframe>
    source: 'openwebcamdb' as const,
    active: true,
  };
}

export async function GET() {
  if (!API_KEY) {
    return NextResponse.json(
      { error: 'OPENWEBCAMDB_API_KEY not configured' },
      { status: 503 }
    );
  }

  if (cache && Date.now() - cache.at < CACHE_TTL) {
    return NextResponse.json(cache.data);
  }

  try {
    // Fetch 1 page of 50 webcams — stays well within 5 req/min rate limit.
    // Cached for 1 hour so we only spend 1 API call per server restart.
    const items = await fetchPage(1, 50);
    const cameras = items.map(toCamera).filter((c): c is CCTVCamera => c !== null);

    cache = { data: cameras, at: Date.now() };
    return NextResponse.json(cameras, {
      headers: { 'Cache-Control': 'public, s-maxage=3600' },
    });
  } catch {
    if (cache) return NextResponse.json(cache.data); // serve stale on error
    return NextResponse.json([], { status: 502 });
  }
}

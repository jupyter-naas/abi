import { NextRequest, NextResponse } from 'next/server';

const API_KEY = process.env.OPENWEBCAMDB_API_KEY?.replace(/^"|"$/g, '') ?? '';
const BASE    = 'https://openwebcamdb.com/api/v1';

// Cache resolved stream URLs for 30 minutes to preserve daily quota
const streamCache = new Map<string, { url: string; type: string; at: number }>();
const STREAM_TTL  = 30 * 60 * 1000;

interface WebcamDetailResponse {
  data: {
    slug: string;
    title: string;
    stream_url?: string;
    stream_type?: string;   // 'youtube' | 'iframe'
  };
}

function youtubeVideoId(url: string): string | null {
  const m = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|live\/|embed\/))([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

function resolveEmbedUrl(raw: string, streamType: string): { url: string; type: 'youtube' | 'youtube' } {
  if (streamType === 'youtube' || youtubeVideoId(raw)) {
    const vid = youtubeVideoId(raw);
    return {
      url: vid
        ? `https://www.youtube.com/embed/${vid}?autoplay=1&mute=1&controls=1`
        : raw,
      type: 'youtube',
    };
  }
  // For 'iframe' stream_type: pass the embed URL directly into an <iframe>
  return { url: raw, type: 'youtube' }; // 'youtube' type = rendered as <iframe> in CCTVPanel
}

export async function GET(req: NextRequest) {
  const slug = req.nextUrl.searchParams.get('slug');
  if (!slug) return NextResponse.json({ error: 'missing slug' }, { status: 400 });
  if (!API_KEY) return NextResponse.json({ error: 'API key not configured' }, { status: 503 });

  const cached = streamCache.get(slug);
  if (cached && Date.now() - cached.at < STREAM_TTL) {
    return NextResponse.json({ url: cached.url, type: cached.type });
  }

  try {
    const res = await fetch(`${BASE}/webcams/${slug}`, {
      headers: {
        Authorization: `Bearer ${API_KEY}`,
        'User-Agent': 'WorldView/1.0',
        Accept: 'application/json',
      },
      signal: AbortSignal.timeout(8000),
    });

    if (!res.ok) {
      const body = await res.text();
      return NextResponse.json({ error: `upstream ${res.status}: ${body.slice(0, 120)}` }, { status: res.status });
    }

    const detail = (await res.json()) as WebcamDetailResponse;
    const raw = detail.data?.stream_url ?? '';
    const streamType = detail.data?.stream_type ?? 'iframe';

    if (!raw) {
      return NextResponse.json({ error: 'no stream_url in response' }, { status: 404 });
    }

    const { url, type } = resolveEmbedUrl(raw, streamType);
    streamCache.set(slug, { url, type, at: Date.now() });
    return NextResponse.json({ url, type });
  } catch {
    return NextResponse.json({ error: 'fetch error' }, { status: 502 });
  }
}

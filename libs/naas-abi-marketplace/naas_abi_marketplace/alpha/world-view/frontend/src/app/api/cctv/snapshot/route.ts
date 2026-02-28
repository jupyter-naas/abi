/**
 * Server-side proxy that fetches a CCTV camera image/stream.
 * For TfL JamCam JPEG: proxies the image with proper CORS headers.
 * For 511NY HLS: fetches the m3u8 playlist and redirects to latest TS segment.
 */
import { NextRequest, NextResponse } from 'next/server';

// Cache snapshots briefly to reduce external requests
const snapCache = new Map<string, { buf: ArrayBuffer; ct: string; at: number }>();
const SNAP_TTL = 4000; // 4 seconds

export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get('url');
  if (!url) return NextResponse.json({ error: 'missing url' }, { status: 400 });

  const cached = snapCache.get(url);
  if (cached && Date.now() - cached.at < SNAP_TTL) {
    return new NextResponse(cached.buf, {
      headers: {
        'Content-Type': cached.ct,
        'Cache-Control': 'public, max-age=4',
        'Access-Control-Allow-Origin': '*',
      },
    });
  }

  try {
    let fetchUrl = url;

    // For HLS playlists: parse m3u8 and redirect to latest .ts segment
    if (url.endsWith('.m3u8')) {
      const m3u8Res = await fetch(url, {
        headers: { 'User-Agent': 'WorldView/1.0' },
        signal: AbortSignal.timeout(5000),
      });
      if (!m3u8Res.ok) {
        return NextResponse.json({ error: 'HLS fetch failed' }, { status: 502 });
      }
      const m3u8Text = await m3u8Res.text();
      // Extract segment URLs from the playlist
      const lines = m3u8Text.split('\n').filter((l) => l.trim() && !l.startsWith('#'));
      if (lines.length === 0) {
        return NextResponse.json({ error: 'empty playlist' }, { status: 502 });
      }
      // Use the last segment (most recent)
      const segment = lines[lines.length - 1].trim();
      // Resolve relative URLs
      const baseUrl = url.substring(0, url.lastIndexOf('/') + 1);
      fetchUrl = segment.startsWith('http') ? segment : baseUrl + segment;
    }

    const res = await fetch(fetchUrl, {
      headers: { 'User-Agent': 'WorldView/1.0' },
      signal: AbortSignal.timeout(6000),
    });

    if (!res.ok) {
      return NextResponse.json({ error: `upstream ${res.status}` }, { status: 502 });
    }

    const ct = res.headers.get('content-type') ?? 'application/octet-stream';
    const buf = await res.arrayBuffer();

    snapCache.set(url, { buf, ct, at: Date.now() });
    // Prevent unbounded cache growth
    if (snapCache.size > 500) {
      const oldest = [...snapCache.entries()].sort((a, b) => a[1].at - b[1].at)[0];
      snapCache.delete(oldest[0]);
    }

    return new NextResponse(buf, {
      headers: {
        'Content-Type': ct,
        'Cache-Control': 'public, max-age=4',
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch {
    return NextResponse.json({ error: 'proxy error' }, { status: 502 });
  }
}
